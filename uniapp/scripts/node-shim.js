/**
 * Node 兼容 shim（node >= 19 移除了 util.isRegExp 等旧 API）。
 * uni-app 编译链中的老包（如 postcss-urlrewrite）仍依赖它们，
 * 通过 `node -r ./scripts/node-shim.js` 在编译前注入。
 */
const util = require('util')

if (!util.isRegExp) {
  util.isRegExp = (v) => Object.prototype.toString.call(v) === '[object RegExp]'
}
if (!util.isDate) {
  util.isDate = (v) => Object.prototype.toString.call(v) === '[object Date]'
}
if (!util.isArray) {
  util.isArray = Array.isArray
}
if (!util.isObject) {
  util.isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)
}
