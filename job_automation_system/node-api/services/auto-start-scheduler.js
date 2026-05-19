/**
 * Auto-Start Scheduler - Job Automation System
 * ===========================================
 * Monitors the current time and automatically starts workers 
 * at the predefined schedule times (6AM, 11AM, 5PM, 8PM).
 */

const { dockerManager } = require('./docker-manager');

const SCHEDULED_TIMES = ['06:00', '11:00', '17:00', '20:00'];
const CHECK_INTERVAL_MS = 60000; // Check every minute

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

        if (SCHEDULED_TIMES.includes(currentTime)) {
            console.log(`[AutoStart] Scheduled time reached: ${currentTime}. Starting workers...`);
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
                    await this.redis.set('automation:start_reason', `scheduled-${currentTime}`);
                    
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
        console.log('[AutoStart] Scheduler active. Scheduled times:', SCHEDULED_TIMES.join(', '));
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
