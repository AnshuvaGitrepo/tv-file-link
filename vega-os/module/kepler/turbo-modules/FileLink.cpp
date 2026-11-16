#include "FileLink.h"
#include "Transfer.h"

namespace FileLinkModule {
FileLink::FileLink() = default;
FileLink::~FileLink() noexcept = default;

std::string FileLink::operate(std::string root, std::string action,
                              std::string path, std::string name) {
    return filelink::operate(root, action, path, name);
}
}
