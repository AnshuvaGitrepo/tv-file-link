const path = require('node:path');
const {getDefaultConfig, mergeConfig} = require('@react-native/metro-config');

const defaults = getDefaultConfig(__dirname);
const moduleRoot = path.resolve(__dirname, 'module');
function exclude(folder) {
  const escaped = path.join(moduleRoot, folder).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp('^' + escaped + '[/\\\\].*');
}

module.exports = mergeConfig(defaults, {
  resolver: {
    blockList: [defaults.resolver.blockList, exclude('build'), exclude('node_modules')].flat().filter(Boolean),
  },
});
