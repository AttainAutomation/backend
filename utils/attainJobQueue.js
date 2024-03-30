import Bull from "bull";
import dotenv from "dotenv";
import { spawn } from "child_process";
import { sendEmail } from "./email.js";

dotenv.config();

const jobQueue = new Bull("attainJobQueue", {
  redis: {
    host: process.env.REDIS_HOST, // e.g., '127.0.0.1'
    port: process.env.REDIS_PORT, // e.g., 6379
  },
});
await jobQueue.empty();

const CONCURRENCY = 6;

jobQueue.process(CONCURRENCY, async (job) => {
  const { filePath, username, password, type } = job.data;
  let automationPath;
  switch (type) {
    case "fritolay": {
      automationPath = "./automations/fritolay_bot.py";
      break;
    }
    case "kehe": {
      automationPath = "./automations/kehe_bot.py";
      break;
    }
    case "coremark": {
      automationPath = "./automations/coremark_bot.py";
      break;
    }
    default: {
      return;
    }
  }
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn("python3.11", [
      "-u",
      automationPath,
      "-f",
      filePath,
      "-u",
      username,
      "-p",
      password,
    ]);

    pythonProcess.stdout.on("data", (data) => {
      console.log(`stdout: ${data}`);
    });

    pythonProcess.stderr.on("data", (data) => {
      console.error(`stderr: ${data}`);
    });

    pythonProcess.on("close", (code) => {
      if (code === 0) {
        resolve(`Process completed with code ${code}`);
      } else {
        reject(`Process failed with code ${code}`);
      }
    });
  });
});

function scheduleJob(filePath, username, password, email, type) {
  const fileName = filePath.split("/")[1] + ".csv";
  console.log(fileName);
  jobQueue.add({ filePath, username, password, type }).then((job) => {
    job
      .finished()
      .then(async () => {
        console.log(`Attain ${type} job ${job.id} completed`);
        sendEmail(
          email,
          `Attain ${type} Job Completed`,
          `Your Attain ${type} job has completed. The csv in attached below.`,
          [{ fileName: fileName, path: "results/" + fileName }]
        );
      })
      .catch((error) => {
        sendEmail(email, `Attain ${type} Job Failed`, error.toString(), [
          { fileName: "screenshot.jpg", path: "screenshot.jpg" },
        ]);
        console.error(`Attain ${type} job ${job.id} failed`, error);
      });
  });
}

export { scheduleJob, jobQueue };
