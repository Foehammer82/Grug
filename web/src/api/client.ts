import axios from 'axios';
import { getEnv } from '../env';

const client = axios.create({
  baseURL: getEnv('VITE_API_URL') ?? 'http://localhost:8000',
  withCredentials: true,
});

export default client;
