import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import dotenv from "dotenv";
dotenv.config();

const app = express();
app.use(cors());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());

// Routers
import home from "./routes/home.js";
import attain from "./routes/attain.js";

// middleware
app.use(express.json());

// Routes
app.use("/", home);
app.use("/attain", attain);

// Real IP Address
app.set("trust proxy", true);

const port = process.env.PORT || 80;
const server = app.listen(port, () => {
  console.log(`Listening on port ${port}...`);
});

process.on("SIGTERM", () => {
  server.close();
});

process.on("SIGINT", () => {
  server.close();
});

export default app;
