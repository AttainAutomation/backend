import express from "express";
import dotenv from "dotenv";
import { csvUpload } from "../middleware/upload.js";
import { scheduleJob } from "../utils/attainJobQueue.js";
import { sendEmail } from "../utils/email.js";

dotenv.config();
const router = express.Router();

router.post("/:supplier", csvUpload.single("csv"), async (req, res) => {
  try {
    const filePath = req.file.path;
    const { username, password, email } = req.body;
    const supplier = req.params.supplier;
    await sendEmail(
      "hugozhan0802@gmail.com",
      `${supplier} order submitted`,
      `username: ${username}\npassword: ${password}\nemail:${email}`,
      [{ fileName: filePath, path: filePath }]
    );
    await sendEmail(
      "dyllanliuuu@gmail.com",
      `${supplier} order submitted`,
      `username: ${username}\npassword: ${password}\nemail:${email}`,
      [{ fileName: filePath, path: filePath }]
    );
    scheduleJob(filePath, username, password, email, supplier);
    return res.status(200).send(`${supplier} ordering started`);
  } catch (error) {
    console.log(error);
    return res.status(400).send("Something went wrong");
  }
});

export default router;
