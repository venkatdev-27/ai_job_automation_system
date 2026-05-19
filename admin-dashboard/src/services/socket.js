import { io } from 'socket.io-client';

const socket = io(import.meta.env.VITE_API_URL || '', { transports: ['websocket', 'polling'], reconnection: true, reconnectionDelay: 2000 });

socket.on('connect', () => console.log('✅ Socket connected:', socket.id));
socket.on('disconnect', () => console.log('❌ Socket disconnected'));

export default socket;
