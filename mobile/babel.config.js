module.exports = {
  presets: ["module:@react-native/babel-preset"],
  plugins: [
    [
      "module-resolver",
      {
        root: ["./src"],
        extensions: [".ios.ts", ".android.ts", ".ts", ".tsx", ".js", ".json"],
        alias: {
          "@": "./src",
        },
      },
    ],
  ],
};
