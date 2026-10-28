import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "#EDEFE7",
        panel: "#F7F7F1",
        ink: {
          DEFAULT: "#16211F",
          soft: "#4B5751",
          faint: "#7C867F",
        },
        rule: "#CBD1C5",
        seal: {
          DEFAULT: "#A33A28",
          soft: "#F2E2DC",
        },
        teal: {
          DEFAULT: "#0E4A45",
          soft: "#DCE7E1",
        },
        turmeric: {
          DEFAULT: "#A97612",
          soft: "#F4EAD3",
        },
        indigo: {
          DEFAULT: "#394A78",
          soft: "#E1E5EF",
        },
        plum: {
          DEFAULT: "#6A3F5C",
          soft: "#EDE2E9",
        },
      },
      fontFamily: {
        sans: ["var(--font-public-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-spectral)", "Georgia", "serif"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      boxShadow: {
        slip: "0 1px 0 0 rgba(22, 33, 31, 0.04)",
      },
      keyframes: {
        "sweep-in": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "sweep-in": "sweep-in 320ms cubic-bezier(0.2, 0.7, 0.2, 1) both",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
