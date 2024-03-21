import express from "express";
import dotenv from "dotenv";
import { csvUpload } from "../middleware/upload.js";
import { scheduleJob } from "../utils/attainJobQueue.js";

dotenv.config();
const router = express.Router();

router.post("/:supplier", csvUpload.single("csv"), async (req, res) => {
  try {
    const filePath = req.file.path;
    const { username, password, email } = req.body;
    const supplier = req.params.supplier;
    scheduleJob(filePath, username, password, email, supplier);
    return res.status(200).send(`${supplier} ordering started`);
  } catch (error) {
    console.log(error);
    return res.status(400).send("Something went wrong");
  }
});

export default router;
