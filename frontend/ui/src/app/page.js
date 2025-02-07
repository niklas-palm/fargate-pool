"use client"; // Add this at the top of the file

import { useState, useEffect } from "react";
import axios from "axios";

export default function Home() {
  const [taskCounts, setTaskCounts] = useState({
    launching: 0,
    available: 0,
    occupied: 0,
  });
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get("http://localhost:5001/monitor");
        setTaskCounts(response.data);
      } catch (error) {
        console.error("Error fetching task counts:", error);
      }
    };

    fetchData(); // Fetch immediately on mount
    const interval = setInterval(fetchData, 1000); // Then fetch every second

    return () => clearInterval(interval); // Clean up on unmount
  }, []);

  const grabTask = async () => {
    setIsLoading(true);
    const userId = Math.random().toString(36).substring(7); // Generate random user ID
    try {
      const response = await axios.post("http://localhost:5001/grab-task", {
        user_id: userId,
      });
      console.log(
        `Task grabbed! Task ID: ${response.data.task_id}, IP: ${response.data.public_ip}`
      );
    } catch (error) {
      console.log(
        "Failed to grab task: " + (error.response?.data?.error || error.message)
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="grid grid-rows-[auto_1fr_auto] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20 font-[family-name:var(--font-geist-sans)]">
      <header className="w-full text-center">
        <h1 className="text-2xl font-bold mb-4">Task Pool Monitor</h1>
      </header>

      <main className="flex flex-col gap-8 items-center sm:items-start w-full max-w-2xl">
        <div className="grid grid-cols-3 gap-4 w-full">
          {Object.entries(taskCounts).map(([status, count]) => (
            <div
              key={status}
              className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg text-center"
            >
              <h2 className="text-lg font-semibold capitalize">{status}</h2>
              <p className="text-3xl font-bold">{count}</p>
            </div>
          ))}
        </div>

        <button
          onClick={grabTask}
          disabled={isLoading}
          className="rounded-full border border-solid border-transparent transition-colors flex items-center justify-center bg-blue-500 text-white gap-2 hover:bg-blue-600 text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? "Grabbing..." : "Grab a Task"}
        </button>
      </main>
    </div>
  );
}
