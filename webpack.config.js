const path = require("path");

module.exports = {
  mode: "production",
  entry: "./dashboard/src/app.js",
  output: {
    filename: "bundle.js",
    path: path.resolve(__dirname, "dashboard/dist"),
  },
};
