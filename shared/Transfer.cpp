#include "Transfer.h"
#include "Portal.h"
#include "vendor/httplib.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <deque>
#include <sstream>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <random>
#include <stdexcept>
#include <thread>
#include <arpa/inet.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <unistd.h>

namespace filelink {
namespace fs = std::filesystem;
namespace {
constexpr size_t maxUpload = 2147483647;
constexpr char tempPrefix[] = ".tvlink-";
std::mutex files;
std::mutex session;

using Clock = std::chrono::steady_clock;
constexpr size_t maxDevices = 8;

// Wrong-code tracking for one browser address.
struct Attempts {
    std::deque<Clock::time_point> failures;
    int streak = 0;
    Clock::time_point lockedUntil{};
};

struct Receiver {
    std::atomic<bool> stopping{false};
    std::mutex pairing;
    std::map<std::string, Attempts> attempts;      // by browser IP
    std::deque<Clock::time_point> allFailures;     // all browsers together
    std::map<std::string, std::string> keys;       // access key -> browser IP
    httplib::Server http;
    std::thread worker;
    std::string address;
    ~Receiver() {
        stopping = true;
        http.stop();
        if (worker.joinable()) worker.join();
    }
};

std::unique_ptr<Receiver> receiver;

struct Failure : std::runtime_error {
    int status;
    Failure(int code, const std::string& message) : std::runtime_error(message), status(code) {}
};

std::string makeKey() {
    std::random_device random;
    std::uniform_int_distribution<unsigned> digit(0, 15);
    const char* hex = "0123456789abcdef";
    std::string key;
    for (int i = 0; i < 32; ++i) key += hex[digit(random)];
    return key;
}

std::string quote(const std::string& value) {
    std::string result = "\"";
    const char* hex = "0123456789abcdef";
    for (unsigned char ch : value) {
        if (ch == '"' || ch == '\\') {
            result += '\\';
            result += ch;
        } else if (ch < 32) {
            result += "\\u00";
            result += hex[ch >> 4];
            result += hex[ch & 15];
        } else {
            result += ch;
        }
    }
    return result + '"';
}

bool validName(const std::string& name) {
    if (name.empty() || name.size() > 255 || name == "." || name == ".." ||
        name.rfind(tempPrefix, 0) == 0) return false;
    return std::none_of(name.begin(), name.end(), [](unsigned char ch) {
        return ch < 32 || ch == 127 || ch == '/' || ch == '\\';
    });
}

fs::path resolve(const fs::path& root, const std::string& path) {
    fs::path result = root;
    if (path.empty()) return result;
    if (path.size() > 3000 || path.back() == '/') throw Failure(400, "Invalid path.");
    std::istringstream segments(path);
    for (std::string part; std::getline(segments, part, '/');) {
        if (!validName(part)) throw Failure(400, "Invalid path.");
        result /= part;
        if (fs::is_symlink(result)) throw Failure(400, "This path is unavailable.");
    }
    return result;
}

long long modifiedSeconds(const fs::path& path) {
    std::error_code error;
    const auto stamp = fs::last_write_time(path, error);
    if (error) return 0;
    // file_time_type -> seconds since the Unix epoch (C++17-portable conversion)
    const auto now = fs::file_time_type::clock::now();
    const auto sys = std::chrono::system_clock::now() +
        std::chrono::duration_cast<std::chrono::system_clock::duration>(stamp - now);
    return std::chrono::duration_cast<std::chrono::seconds>(sys.time_since_epoch()).count();
}

std::string list(const fs::path& path) {
    if (!fs::is_directory(path)) throw Failure(404, "Folder unavailable. Refresh the list.");
    std::vector<fs::directory_entry> entries;
    for (const auto& item : fs::directory_iterator(path)) {
        if (!validName(item.path().filename().string()) || item.is_symlink()) continue;
        if (item.is_directory() || item.is_regular_file()) entries.push_back(item);
    }
    std::sort(entries.begin(), entries.end(), [](const auto& left, const auto& right) {
        if (left.is_directory() != right.is_directory()) return left.is_directory();
        return left.path().filename() < right.path().filename();
    });
    std::string json = "[";
    for (const auto& item : entries) {
        if (json.size() > 1) json += ',';
        const bool folder = item.is_directory();
        json += "{\"name\":" + quote(item.path().filename().string()) +
            ",\"folder\":" + (folder ? "true" : "false") +
            ",\"size\":" + std::to_string(folder ? 0 : item.file_size()) +
            ",\"modified\":" + std::to_string(modifiedSeconds(item.path())) + "}";
    }
    return json + ']';
}

std::string localAddress() {
    ifaddrs* interfaces = nullptr;
    if (getifaddrs(&interfaces) != 0) return {};
    std::unique_ptr<ifaddrs, decltype(&freeifaddrs)> guard(interfaces, freeifaddrs);
    int best = 0;
    std::string address;
    for (auto* entry = interfaces; entry; entry = entry->ifa_next) {
        if (!entry->ifa_addr || entry->ifa_addr->sa_family != AF_INET ||
            !(entry->ifa_flags & IFF_UP) || (entry->ifa_flags & IFF_LOOPBACK)) continue;
        const std::string name = entry->ifa_name;
        const int score = name.rfind("wlan", 0) == 0 ? 3 :
                          name.rfind("eth", 0) == 0 ? 2 : 0;
        if (score <= best) continue;
        char ip[INET_ADDRSTRLEN];
        const auto* ipv4 = reinterpret_cast<sockaddr_in*>(entry->ifa_addr);
        if (inet_ntop(AF_INET, &ipv4->sin_addr, ip, sizeof(ip))) {
            address = ip;
            best = score;
        }
    }
    return address;
}

void serveUpload(const fs::path& root, const httplib::Request& req, httplib::Response& res,
                 const httplib::ContentReader& read, const std::atomic<bool>& stopping) {
    const auto name = req.get_param_value("name");
    if (!validName(name)) throw Failure(400, "Invalid file name.");
    const auto folder = req.get_param_value("path");
    fs::path target;
    {
        std::lock_guard<std::mutex> lock(files);
        const auto parent = resolve(root, folder);
        if (!fs::is_directory(parent)) throw Failure(404, "Destination folder unavailable.");
        target = parent / name;
        if (fs::exists(fs::symlink_status(target)))
            throw Failure(409, "\"" + name + "\" already exists in this folder. Rename the file and upload it again.");
    }
    const auto staging = root / ".tvlink-staging";
    fs::create_directories(staging);
    std::string temp = (staging / "upload-XXXXXX").string();
    const int fd = mkstemp(temp.data());
    if (fd < 0) throw Failure(507, "Could not open storage for the upload.");
    struct TempFile {
        std::string path;
        int fd;
        ~TempFile() {
            if (fd >= 0) close(fd);
            unlink(path.c_str());
        }
    } partial{temp, fd};
    size_t written = 0;
    bool tooLarge = false;
    bool diskError = false;
    const bool complete = read([&](const char* bytes, size_t length) {
        if (stopping) return false;
        if (length > maxUpload - written) {
            tooLarge = true;
            return false;
        }
        while (length) {
            const auto count = write(fd, bytes, length);
            if (count < 0 && errno == EINTR) continue;
            if (count <= 0) {
                diskError = true;
                return false;
            }
            written += count;
            bytes += count;
            length -= count;
        }
        return true;
    });
    if (tooLarge) throw Failure(413, "The upload limit is 2 GiB per file.");
    if (diskError) throw Failure(507, "Could not save the file. Check free space.");
    if (!complete || stopping) throw Failure(400, "Upload interrupted.");
    if (fsync(fd) != 0) throw Failure(507, "Could not save the file. Check free space.");
    std::lock_guard<std::mutex> lock(files);
    target = resolve(root, folder) / name;
    if (fs::exists(fs::symlink_status(target)))
        throw Failure(409, "\"" + name + "\" already exists in this folder. Rename the file and upload it again.");
    fs::rename(temp, target);
    res.status = 201;
    res.set_content("Saved.", "text/plain");
}

template <typename Action>
void respond(httplib::Response& res, Action action) {
    try {
        action();
    } catch (const Failure& error) {
        res.status = error.status;
        res.set_content(error.what(), "text/plain; charset=utf-8");
    } catch (const std::exception&) {
        res.status = 500;
        res.set_content("Could not access storage. Check free space and try again.", "text/plain");
    }
}

std::string start(const fs::path& root, std::string ip) {
    std::lock_guard<std::mutex> lock(session);
    if (receiver) return receiver->address;
    if (ip.empty()) ip = localAddress();
    if (ip.empty()) throw Failure(400, "Connect your Fire TV to Wi-Fi or Ethernet first.");
    std::random_device random;
    const auto number = std::uniform_int_distribution<unsigned>(0, 999999)(random);
    const std::string code = std::to_string(1000000 + number).substr(1);  // keeps leading zeros
    auto next = std::make_unique<Receiver>();
    auto& http = next->http;
    auto& stopping = next->stopping;
    http.set_read_timeout(5, 0);
    http.set_write_timeout(5, 0);
    http.set_keep_alive_max_count(1);
    http.set_payload_max_length(maxUpload);
    http.new_task_queue = [] { return new httplib::ThreadPool(4, 8); };
    http.set_default_headers({
        {"Cache-Control", "no-store"}, {"Referrer-Policy", "no-referrer"},
        {"X-Content-Type-Options", "nosniff"},
        {"Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}
    });
    // Every /api/ call except connect needs a key issued by this session to this browser address.
    http.set_pre_routing_handler([state = next.get()](const httplib::Request& req, httplib::Response& res) {
        if (req.path.rfind("/api/", 0) != 0 || req.path == "/api/connect") return httplib::Server::HandlerResponse::Unhandled;
        const auto supplied = req.path == "/api/download" ? req.get_param_value("key") :
            req.get_header_value("X-Transfer-Key");
        {
            std::lock_guard<std::mutex> lock(state->pairing);
            const auto found = state->keys.find(supplied);
            if (!state->stopping && !supplied.empty() && found != state->keys.end() &&
                found->second == req.remote_addr) return httplib::Server::HandlerResponse::Unhandled;
        }
        res.status = 403;
        res.set_content("This transfer session has ended. Enter the current code from your TV.", "text/plain");
        return httplib::Server::HandlerResponse::Handled;
    });
    http.Get("/", [](const httplib::Request&, httplib::Response& res) {
        res.set_content(portalHtml, "text/html; charset=utf-8");
    });
    http.Post("/api/connect", [code, state = next.get()](const auto& req, auto& res) {
        respond(res, [&] {
            std::lock_guard<std::mutex> lock(state->pairing);
            if (state->stopping) throw Failure(403, "Start transfer on your TV first.");
            const auto now = Clock::now();
            auto prune = [now](std::deque<Clock::time_point>& list) {
                while (!list.empty() && now - list.front() >= std::chrono::minutes(1)) list.pop_front();
            };
            auto& mine = state->attempts[req.remote_addr];
            prune(mine.failures);
            prune(state->allFailures);
            if (now < mine.lockedUntil) {
                const auto wait = std::chrono::duration_cast<std::chrono::seconds>(
                    mine.lockedUntil - now).count() + 1;
                throw Failure(429, "Too many wrong codes. Wait " + std::to_string(wait) +
                              (wait == 1 ? " second" : " seconds") + " and try again.");
            }
            if (mine.failures.size() >= 10 || state->allFailures.size() >= 30)
                throw Failure(429, "Too many attempts. Wait a minute and try again.");
            if (req.get_header_value("X-TV-Code") != code) {
                mine.failures.push_back(now);
                state->allFailures.push_back(now);
                // After 3 wrong codes in a row: wait 1, 2, 4 ... up to 60 seconds.
                if (++mine.streak >= 3)
                    mine.lockedUntil = now + std::chrono::seconds(std::min(60, 1 << std::min(mine.streak - 3, 6)));
                throw Failure(403, "That code is not correct. Enter the six-digit code shown on your TV.");
            }
            mine.streak = 0;
            if (state->keys.size() >= maxDevices)
                throw Failure(429, "Too many devices are connected. Stop and restart the transfer on your TV.");
            const auto key = makeKey();
            state->keys[key] = req.remote_addr;
            res.set_content(quote(key), "application/json");
        });
    });
    http.Get("/api/list", [root](const auto& req, auto& res) {
        respond(res, [&] {
            std::lock_guard<std::mutex> lock(files);
            res.set_content(list(resolve(root, req.get_param_value("path"))), "application/json");
        });
    });
    http.Get("/api/download", [root, &stopping](const auto& req, auto& res) {
        respond(res, [&] {
            std::lock_guard<std::mutex> lock(files);
            const auto path = resolve(root, req.get_param_value("path"));
            if (!fs::is_regular_file(path)) throw Failure(404, "File unavailable. Refresh the list.");
            auto stream = std::make_shared<std::ifstream>(path, std::ios::binary);
            if (!*stream) throw Failure(404, "File unavailable. Refresh the list.");
            const auto size = fs::file_size(path);
            res.set_header("Content-Disposition", "attachment; filename*=UTF-8''" +
                           httplib::encode_uri_component(path.filename().string()));
            res.set_content_provider(size, "application/octet-stream",
                [stream, &stopping](size_t offset, size_t length, httplib::DataSink& sink) {
                    if (stopping) return false;
                    char buffer[65536];
                    const auto count = std::min(length, sizeof(buffer));
                    stream->seekg(offset);
                    stream->read(buffer, count);
                    return static_cast<size_t>(stream->gcount()) == count && sink.write(buffer, count);
                });
        });
    });
    http.Post("/api/upload", [root, &stopping](const httplib::Request& req, httplib::Response& res,
                                   const httplib::ContentReader& read) {
        respond(res, [&] {
            if (req.get_header_value("Content-Type") != "application/octet-stream")
                throw Failure(415, "Choose a file in the transfer page.");
            serveUpload(root, req, res, read, stopping);
        });
    });
    const int port = http.bind_to_any_port(ip);
    if (port < 0) throw Failure(500, "Could not open Wi-Fi Transfer on this network.");
    next->address = "http://" + ip + ":" + std::to_string(port) + " " + code;
    next->worker = std::thread([&http] { http.listen_after_bind(); });
    http.wait_until_ready();
    if (!http.is_running()) throw Failure(500, "Could not start Wi-Fi Transfer.");
    receiver = std::move(next);
    return receiver->address;
}

std::string manage(const fs::path& root, const std::string& action,
                   const std::string& path, const std::string& name) {
    std::lock_guard<std::mutex> lock(files);
    const auto item = resolve(root, path);
    if (action == "list") return list(item);
    if (action == "delete") {
        if (item == root) throw Failure(400, "My files cannot be deleted.");
        std::error_code error;
        const bool removed = fs::remove(item, error);
        if (error == std::errc::directory_not_empty) throw Failure(409, "Empty this folder before deleting it.");
        if (error || !removed) throw Failure(404, "This item could not be deleted. Refresh the list.");
        return "null";
    }
    // ---- file manager actions (used by the Vega edition; Fire OS does these in Java)
    if (action == "rmtree") {  // folder with contents, after the user confirmed
        if (item == root) throw Failure(400, "My files cannot be deleted.");
        std::error_code error;
        fs::remove_all(item, error);
        if (error) throw Failure(500, "Some items could not be deleted. Refresh the list.");
        return "null";
    }
    if (action == "stat") {
        if (!fs::exists(item)) throw Failure(404, "This item is no longer available.");
        std::uintmax_t size = 0, items = 0;
        if (fs::is_directory(item)) {
            for (const auto& entry : fs::recursive_directory_iterator(item)) {
                if (!validName(entry.path().filename().string())) continue;
                ++items;
                if (entry.is_regular_file()) size += entry.file_size();
            }
        } else {
            size = fs::file_size(item);
        }
        return "{\"size\":" + std::to_string(size) + ",\"items\":" + std::to_string(items) +
            ",\"modified\":" + std::to_string(modifiedSeconds(item)) + "}";
    }
    if (action == "read") {  // text viewer: first 256 KiB, invalid UTF-8 shown as '?'
        if (!fs::is_regular_file(item)) throw Failure(404, "File unavailable. Refresh the list.");
        std::ifstream in(item, std::ios::binary);
        std::string data(262144, '\0');
        in.read(&data[0], data.size());
        data.resize(static_cast<size_t>(in.gcount()));
        std::string clean;
        for (size_t i = 0; i < data.size();) {
            const unsigned char ch = data[i];
            const size_t len = ch < 0x80 ? 1 : (ch >> 5) == 6 ? 2 : (ch >> 4) == 14 ? 3 : (ch >> 3) == 30 ? 4 : 0;
            bool valid = len && i + len <= data.size();
            for (size_t k = 1; valid && k < len; ++k) valid = (static_cast<unsigned char>(data[i + k]) >> 6) == 2;
            if (valid) { clean.append(data, i, len); i += len; } else { clean += '?'; ++i; }
        }
        return quote(clean);
    }
    if (action == "copy" || action == "move") {  // name = destination folder inside the library
        if (item == root) throw Failure(400, "Choose a file or folder first.");
        if (!fs::exists(fs::symlink_status(item))) throw Failure(404, "This item is no longer available.");
        const auto destination = resolve(root, name);
        if (!fs::is_directory(destination)) throw Failure(404, "Destination folder unavailable.");
        const auto src = fs::weakly_canonical(item).string();
        const auto dst = fs::weakly_canonical(destination).string();
        if (fs::is_directory(item) && (dst == src || dst.rfind(src + "/", 0) == 0))
            throw Failure(400, "A folder cannot be copied or moved into itself.");
        if (action == "move" && fs::weakly_canonical(item.parent_path()) == fs::weakly_canonical(destination))
            throw Failure(400, "The item is already in this folder.");
        // free name: "name.ext", "name (1).ext" ...
        const auto filename = item.filename().string();
        const auto dot = fs::is_directory(item) ? std::string::npos : filename.rfind('.');
        const auto base = dot == std::string::npos || dot == 0 ? filename : filename.substr(0, dot);
        const auto ext = dot == std::string::npos || dot == 0 ? std::string() : filename.substr(dot);
        auto target = destination / filename;
        for (int i = 1; fs::exists(fs::symlink_status(target)); ++i)
            target = destination / (base + " (" + std::to_string(i) + ")" + ext);
        std::error_code error;
        if (action == "move") fs::rename(item, target, error);
        else fs::copy(item, target, fs::copy_options::recursive, error);
        if (error) {
            std::error_code ignored;
            if (action == "copy") fs::remove_all(target, ignored);
            throw Failure(507, "Could not finish. Check free space.");
        }
        return quote(target.filename().string());
    }
    if (!validName(name)) throw Failure(400, "Enter a valid file or folder name.");
    if (action == "mkdir") {
        if (!fs::create_directory(item / name)) throw Failure(409, "This folder already exists.");
    } else if (action == "rename" && item != root) {
        const auto target = item.parent_path() / name;
        if (target == item) return "null";
        if (fs::exists(fs::symlink_status(target))) throw Failure(409, "This name is already in use.");
        fs::rename(item, target);
    } else {
        throw Failure(400, "Unknown file action.");
    }
    return "null";
}
}

std::string operate(const std::string& dir, const std::string& action,
                    const std::string& path, const std::string& name) {
    try {
        if (action == "stop") {
            std::lock_guard<std::mutex> lock(session);
            receiver.reset();
            return "{\"value\":null}";
        }
        const fs::path root(dir);
        fs::create_directories(root);
        const auto result = action == "start" ? quote(start(root, name)) : manage(root, action, path, name);
        return "{\"value\":" + result + "}";
    } catch (const Failure& error) {
        return "{\"error\":" + quote(error.what()) + "}";
    } catch (const std::exception&) {
        return "{\"error\":\"Could not access storage. Refresh the list and try again.\"}";
    }
}
}
