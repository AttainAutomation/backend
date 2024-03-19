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

function scheduleFritoLayJob(filePath, username, password, email) {
  const fileName = filePath.split("/")[1] + ".csv";
  console.log(fileName);
  jobQueue
    .add({ filePath, username, password, type: "fritolay" })
    .then((job) => {
      job
        .finished()
        .then(async () => {
          console.log(`FritoLay job ${job.id} completed`);
          sendEmail(
            email,
            "FritoLay Job Completed",
            "Your FritoLay job has completed. The csv in attached below.",
            [{ fileName: fileName, path: "results/" + fileName }]
          );
        })
        .catch((error) => {
          console.error(`FritoLay job ${job.id} failed`, error);
        });
    });
}

export { scheduleFritoLayJob, jobQueue };
