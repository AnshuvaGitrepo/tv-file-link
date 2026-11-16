#if __has_include(<Kepler/turbomodule/KeplerTurboModuleRegistration.h>)
#include <Kepler/turbomodule/KeplerTurboModuleRegistration.h>
#else
#include <kepler/turbomodule/KeplerTurboModuleRegistration.h>
#endif
#include "turbo-modules/FileLink.h"

extern "C" {
__attribute__((visibility("default"))) void autoLinkKeplerTurboModulesV1() noexcept {
    KEPLER_REGISTER_TURBO_MODULE(FileLinkModule, FileLink);
}
}
