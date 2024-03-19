import dotenv from "dotenv";
import nodemailer from "nodemailer";
dotenv.config();

let mailTransporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    user: "hugozhan0802@gmail.com",
    pass: process.env.GOOGLE_APP_PASS,
  },
});

const sendEmail = async (to, subject, text, attachments = []) => {
  try {
    let mailDetails = {
      from: "hugozhan0802@gmail.com",
      to: to,
      subject: subject,
      text: text,
      attachments: attachments, // Add attachments here
    };
    return await mailTransporter.sendMail(mailDetails);
  } catch (err) {
    console.log(err);
  }
  return;
};

export { sendEmail };
