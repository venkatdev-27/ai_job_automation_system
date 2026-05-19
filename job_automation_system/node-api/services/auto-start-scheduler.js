/**
 * Auto-Start Scheduler - Job Automation System
 * ===========================================
 * Monitors the current time and automatically starts workers 
 * at the predefined schedule times (6AM, 11AM, 5PM, 8PM).
 */

const { dockerManager } = require('./docker-manager');

const DEFAULT_SCHEDULED_TIMES = ['06:00', '11:00', '17:00', '20:00', '22:30'];
const FIXED_BEAT_TIMES = ['20:00', '22:30'];
const CHECK_INTERVAL_MS = 60000; // Check every minute
const PRESTART_MINUTES = 5;

function parseScheduleTimes(value) {
    return String(value || '')
        .split(',')
        .map((item) => item.trim())
        .filter((item) => /^\d{2}:\d{2}$/.test(item));
}

function shiftTimeMinutes(timeValue, deltaMinutes) {
    const [hour, minute] = timeValue.split(':').map(Number);
    const total = (((hour * 60 + minute + deltaMinutes) % 1440) + 1440) % 1440;
    return Math.floor(total / 60).toString().padStart(2, '0') + ':' +
        (total % 60).toString().padStart(2, '0');
}

class AutoStartScheduler {
    constructor(redisClient, io) {
        this.redis = redisClient;
        this.io = io;
        this.intervalId = null;
        this.lastTriggeredMinute = null;
    }

    async check() {
        const now = new Date();
        const currentTime = now.getHours().toString().padStart(2, '0') + ':' + 
                          now.getMinutes().toString().padStart(2, '0');
        
        // Prevent multiple triggers in the same minute
        if (this.lastTriggeredMinute === currentTime) return;

        const configuredSchedule = await this.redis.get('automation:daily_schedule');
        const configuredTimes = parseScheduleTimes(configuredSchedule);
        const scheduledTimes = configuredTimes.length
            ? [...new Set([...configuredTimes, ...FIXED_BEAT_TIMES])]
            : DEFAULT_SCHEDULED_TIMES;
        const prestartTimes = scheduledTimes.map((time) => shiftTimeMinutes(time, -PRESTART_MINUTES));
        const triggerTimes = [...new Set([...prestartTimes, ...scheduledTimes])];

        if (triggerTimes.includes(currentTime)) {
            const nextRun = scheduledTimes.includes(currentTime)
                ? currentTime
                : scheduledTimes.find((time) => shiftTimeMinutes(time, -PRESTART_MINUTES) === currentTime);
            console.log(`[AutoStart] Startup window reached: ${currentTime} (run: ${nextRun || currentTime}). Starting workers...`);
            this.lastTriggeredMinute = currentTime;
            
            try {
                // Check if auto-enable is true in Redis
                const autoEnable = await this.redis.get('automation:auto_enable');
                if (autoEnable !== 'true') {
                    console.log('[AutoStart] Auto-enable is false. Skipping scheduled start.');
                    return;
                }

                const result = await dockerManager.startAll();
                
                if (result.success) {
                    await this.redis.set('automation:main_switch', 'on');
                    await this.redis.set('automation:workers_up', 'true');
                    await this.redis.set('automation:last_start_time', new Date().toISOString());
                    await this.redis.set('automation:start_reason', `scheduled-${nextRun || currentTime}`);
                    
                    console.log(`[AutoStart] Successfully started workers at ${currentTime}`);
                    
                    if (this.io) {
                        this.io.emit('automation_auto_started', {
                            time: currentTime,
                            message: 'Scheduled automation start triggered',
                            workers: result.workersStarted
                        });
                    }
                } else {
                    console.error('[AutoStart] Failed to start workers on schedule:', result.error);
                }
            } catch (error) {
                console.error('[AutoStart] Error during scheduled start:', error.message);
            }
        }
    }

    start() {
        if (this.intervalId) return;
        console.log('[AutoStart] Scheduler active. Default scheduled times:', DEFAULT_SCHEDULED_TIMES.join(', '));
        this.intervalId = setInterval(() => this.check(), CHECK_INTERVAL_MS);
        // Initial check
        this.check();
    }

    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        console.log('[AutoStart] Scheduler stopped');
    }
}

module.exports = { AutoStartScheduler };
