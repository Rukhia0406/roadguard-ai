import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const scanVideo = async (videoFile, latitude = 17.4401, longitude = 78.3489) => {
  const formData = new FormData();
  formData.append('file', videoFile);
  formData.append('latitude', latitude);
  formData.append('longitude', longitude);

  const response = await api.post('/api/v1/scan-video', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getTickets = async () => {
  const response = await api.get('/api/v1/tickets');
  return response.data;
};

export const resolveTicket = async (defectCode) => {
  const response = await api.patch(`/api/v1/tickets/${defectCode}/resolve`);
  return response.data;
};

export default api;