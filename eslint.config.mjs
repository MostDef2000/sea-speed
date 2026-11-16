import globals from "globals";

export default [
  {
    files: ["frontend/**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: {
        ...globals.browser,
        SeaSpeedOverlayCanvas: "readonly",
        SeaSpeedAuth: "readonly",
        SeaSpeedLiveSync: "readonly",
        Hls: "readonly",
        registryScopeKey: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
    },
  },
];
