#include <jni.h>
#include "Transfer.h"

namespace {
std::string read(JNIEnv* env, jbyteArray input) {
    const jsize size = env->GetArrayLength(input);
    std::string value(size, '\0');
    env->GetByteArrayRegion(input, 0, size, reinterpret_cast<jbyte*>(value.data()));
    return value;
}
}

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_anshuva_tvfilelink_MainActivity_nativeOperate(
    JNIEnv* env, jclass, jbyteArray root, jbyteArray action, jbyteArray path, jbyteArray name) {
    const auto result = filelink::operate(read(env, root), read(env, action),
                                         read(env, path), read(env, name));
    const auto size = static_cast<jsize>(result.size());
    jbyteArray bytes = env->NewByteArray(size);
    if (bytes) env->SetByteArrayRegion(bytes, 0, size, reinterpret_cast<const jbyte*>(result.data()));
    return bytes;
}
