const fs = require('node:fs');
const path = require('node:path');

const logo = fs.readFileSync(path.join(__dirname, 'as-logo.png')).toString('base64');
const source = fs.readFileSync(path.join(__dirname, 'portal.html'), 'utf8')
  .replace('{{AS_LOGO}}', logo);
if (source.includes(')PORTAL"')) throw Error('Choose another C++ raw string delimiter.');
fs.writeFileSync(path.join(__dirname, 'Portal.h'),
  '#pragma once\nnamespace filelink {\nconstexpr char portalHtml[] = R"PORTAL(' +
  source + ')PORTAL";\n}\n');
