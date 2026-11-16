#pragma once
#include <string>

namespace filelink {
std::string operate(const std::string& root, const std::string& action,
                    const std::string& path, const std::string& name);
}
