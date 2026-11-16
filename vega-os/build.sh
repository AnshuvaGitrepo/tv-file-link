#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if ! command -v vega >/dev/null; then
  printf '%s\n' 'Install and activate the Vega SDK 2.0 on a supported macOS or Linux host.' >&2
  exit 1
fi
node ../shared/make-portal.cjs
mkdir -p module/shared/vendor
cp ../shared/{Portal.h,Transfer.h,Transfer.cpp} module/shared/
cp ../shared/vendor/{httplib.h,LICENSE} module/shared/vendor/
npm --prefix module run build:js
npm --prefix module run build:native
npx --no-install react-native build-vega --build-type Release
