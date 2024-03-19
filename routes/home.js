import express from "express";

const router = express.Router();

router.get("/", async (req, res) => {
  try {
    res.status(200).send("Welcome to Attain Automation");
  } catch (error) {
    console.log(error);
    res.status(400).send("Something went wrong");
  }
});

export default router;
