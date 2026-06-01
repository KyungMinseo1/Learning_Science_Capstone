module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"] ,
  theme: {
    extend: {
      boxShadow: {
        soft: "0 20px 60px rgba(15, 23, 42, 0.10)",
      },
      backgroundImage: {
        "hero-grid": "linear-gradient(rgba(255,255,255,0.35) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.35) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};
