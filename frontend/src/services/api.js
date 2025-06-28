import axios from 'axios';

// API Base URLs
const YOUTUBE_SEARCH_API = 'https://youtube-search-api-nxbmt7mfiq-uc.a.run.app';
const PRODUCT_SUMMARY_API = 'https://product-summary-api-nxbmt7mfiq-uc.a.run.app';
const PRODUCT_QUERY_API = 'https://product-query-api-nxbmt7mfiq-uc.a.run.app';
const AIRFLOW_SCHEDULER_API = 'https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app';

// YouTube Search API
export const searchYouTube = async (query, maxResults = 5) => {
  try {
    const response = await axios.post(`${YOUTUBE_SEARCH_API}/search`, {
      query,
      max_results: maxResults
    });
    return response.data;
  } catch (error) {
    throw new Error(`YouTube search failed: ${error.message}`);
  }
};

// Product Summary API
export const triggerProductSummary = async () => {
  try {
    const response = await axios.post(`${PRODUCT_SUMMARY_API}/auto-process`);
    return response.data;
  } catch (error) {
    throw new Error(`Product summary generation failed: ${error.message}`);
  }
};

// Product Query API
export const queryProduct = async (productName) => {
  try {
    const response = await axios.post(`${PRODUCT_QUERY_API}/query`, {
      product_name: productName
    });
    return response.data;
  } catch (error) {
    throw new Error(`Product query failed: ${error.message}`);
  }
};

// Airflow Scheduler API
export const scheduleAutomation = async (shoes, waitMinutes = 10, startTime) => {
  try {
    const payload = {
      shoes,
      wait_minutes: waitMinutes
    };
    if (startTime) {
      payload.start_time = startTime;
    }
    const response = await axios.post(`${AIRFLOW_SCHEDULER_API}/schedule`, payload);
    return response.data;
  } catch (error) {
    throw new Error(`Scheduling failed: ${error.message}`);
  }
};

export const getJobStatus = async (jobId) => {
  try {
    const response = await axios.get(`${AIRFLOW_SCHEDULER_API}/jobs/${jobId}`);
    return response.data;
  } catch (error) {
    throw new Error(`Failed to get job status: ${error.message}`);
  }
};

export const listJobs = async (limit = 10) => {
  try {
    const response = await axios.get(`${AIRFLOW_SCHEDULER_API}/jobs?limit=${limit}`);
    return response.data;
  } catch (error) {
    throw new Error(`Failed to list jobs: ${error.message}`);
  }
};

export const cancelJob = async (jobId) => {
  try {
    const response = await axios.delete(`${AIRFLOW_SCHEDULER_API}/jobs/${jobId}`);
    return response.data;
  } catch (error) {
    throw new Error(`Failed to cancel job: ${error.message}`);
  }
};

export const checkHealth = async () => {
  try {
    const response = await axios.get(`${AIRFLOW_SCHEDULER_API}/health`);
    return response.data;
  } catch (error) {
    throw new Error(`Health check failed: ${error.message}`);
  }
}; 