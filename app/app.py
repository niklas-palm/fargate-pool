"use strict";

const express = require("express");

// Constants
const PORT = 8080;
const HOST = "0.0.0.0";
const PODNAME = process.env.HOSTNAME;

// App
const app = express();
app.get("/", (req, res) => {
  res.send(`Hello World! I'm running on task ${PODNAME}`);
});

app.get("/healthcheck", (req, res) => {
  res.send(`${PODNAME}, reporting for duty`);
});

app.listen(PORT, HOST, () => {
  console.log(`Running on http://${HOST}:${PORT}`);
});
