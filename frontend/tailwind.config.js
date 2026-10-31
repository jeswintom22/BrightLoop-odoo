/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brightloop design system — sage green + cream + black type
        sage: {
          DEFAULT: "#A3B18A", // muted sage — primary brand accent
          deep: "#718267", // darker sage — hover/active
          soft: "#E5EBDD", // light sage — selected states, active nav
          faint: "#EFF3E8", // faintest sage — subtle fills
        },
        cream: {
          DEFAULT: "#F6F4EA", // main page background
          card: "#FFFEF8", // card surface
        },
        ink: {
          DEFAULT: "#171A16", // primary text
          muted: "#62665F", // secondary text
        },
        line: "#DFE2D7", // soft neutral border
        success: "#527A55",
        warning: "#A47B36",
        danger: "#AD5750",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        lg: "0.625rem", // 10px
        xl: "0.75rem", // 12px
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(23 26 22 / 0.05)",
      },
    },
  },
  plugins: [],
};
