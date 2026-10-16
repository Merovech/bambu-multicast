// Used only to build client/tailwind.css (npm run build:css).  Nothing here is needed to run the site.
module.exports = {
  content: ["./client/index.html", "./client/app.js"],
  theme: { extend: {} },
  plugins: [],
};
