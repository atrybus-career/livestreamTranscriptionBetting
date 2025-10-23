const express = require('express');
const path = require('path');

const app = express();
const port = 3000;

// Serve static files from the current directory
app.use(express.static(__dirname));

// Route for the main dashboard
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'dashboard.html'));
});

app.listen(port, () => {
  console.log(`Dashboard server is running at http://localhost:${port}`);
});
