/**
 * Auto-Stop Detector - Job Automation System
 * ===========================================
 * Background service that monitors job/student completion
 * and automatically stops workers when all jobs are done.
 * 
 * Auto-stop triggers when ALL conditions are met:
 * 1. MongoDB: 0 students with status 'processing'
 * 2. Redis: jobs_running == 0 for 5+ consecutive minutes
 * 3. Redis: jobs_queue == 0 for 5+ consecutive minutes
 * 4. Minimum runtime (30 min) has passed since START
 * 5. automation:auto_stop == 'true' in Redis
 */

const { dockerManager } = require('./docker-manager');

const AUTO_STOP_CONFIG = {
    checkIntervalMs: 60000,       // Check every 60 seconds
    stableMinutes: 5,              // Jobs must be 0 for 5 minutes before auto-stop
    minRuntimeMinutes: 30,        // Minimum 30 min before auto-stop can trigger
    emitIntervalMs: 30000          // Emit status to clients every 30s
};

const CELERY_QUEUES = ['producer', 'student_wave', 'naukri', 'linkedin', 'foundit', 'warmup'];
const DEFAULT_SCHEDULED_TIMES = ['06:00', '11:00', '17:00', '20:00', '22:30'];

function parseTimeOfDay(value) {
    const match = String(value || '').trim().match(/^(\d{2}):(\d{2})$/);
    if (!match) return null;
    const hour = Number(match[1]);
    const minute = Number(match[2]);
    if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
    return { hour, minute };
}

function hasReachedTimeOfDay(now, timeValue) {
    const parsed = parseTimeOfDay(timeValue);
    if (!parsed) return false;
    return (now.getHours() * 60 + now.getMinutes()) >= (parsed.hour * 60 + parsed.minute);
}

class AutoStopDetector {
    constructor(redisClient, db) {
        this.redis = redisClient;
        this.db = db;
        this.isRunning = false;
        this.intervalId = null;
        this.statusIntervalId = null;
        this.stableStartTime = null;     // When jobs became 0
        this.lastStartTime = null;       // When START was last clicked
        this.lastJobsRunning = 0;
        this.lastJobsQueued = 0;
        this.io = null;
    }

    setSocketIO(io) {
        this.io = io;
    }

    async checkMongoStudentsProcessing() {
        try {
            const collection = this.db.collection('students');
            const count = await collection.countDocuments({ status: 'processing' });
            return count;
        } catch (error) {
            console.error('[AutoStop] MongoDB check failed:', error.message);
            return -1; // Error state - don't trigger auto-stop
        }
    }

    async checkRedisJobStatus() {
        try {
            const jobsRunningRaw = await this.redis.get('automation:jobs_running');
            const jobsRunningParsed = parseInt(jobsRunningRaw || '0', 10);
            const jobsRunning = Number.isFinite(jobsRunningParsed) ? jobsRunningParsed : 0;
            let queueLength = 0;
            for (const queue of CELERY_QUEUES) {
                queueLength += parseInt(await this.redis.llen(queue) || '0', 10);
            }
            const unacked = parseInt(await this.redis.hlen('unacked') || '0', 10);
            const jobsQueued = queueLength + unacked;
            const autoStopEnabled = await this.redis.get('automation:auto_stop');
            const autoOffTime = await this.redis.get('automation:auto_off_time');
            
            return {
                jobsRunning,
                jobsQueued,
                queueLength,
                unacked,
                autoStopEnabled: autoStopEnabled === 'true',
                autoStopEnabledRaw: autoStopEnabled,
                autoOffTime: autoOffTime || '23:59'
            };
        } catch (error) {
            console.error('[AutoStop] Redis check failed:', error.message);
            return { jobsRunning: -1, jobsQueued: -1, autoStopEnabled: false, error: true };
        }
    }

    async getWorkersStatus() {
        try {
            return await dockerManager.getWorkerStatus();
        } catch (error) {
            console.error('[AutoStop] Worker status check failed:', error.message);
            return null;
        }
    }

    async getLastStartTime() {
        try {
            const time = await this.redis.get('automation:last_start_time');
            return time ? new Date(time) : null;
        } catch {
            return null;
        }
    }

    async getBeatTriggerTime() {
        try {
            const time = await this.redis.get('automation:beat_last_trigger_time');
            return time ? new Date(parseInt(time)) : null;
        } catch {
            return null;
        }
    }

    async getSystemStatus() {
        const mongoCount = await this.checkMongoStudentsProcessing();
        const redisStatus = await this.checkRedisJobStatus();
        const workerStatus = await this.getWorkersStatus();
        const lastStart = await this.getLastStartTime();
        const beatTrigger = await this.getBeatTriggerTime();
        
        const now = new Date();
        let minRuntimeMet = true;
        
        // Check either manual start OR beat trigger for min runtime
        const effectiveStart = beatTrigger || lastStart;
        if (effectiveStart) {
            const elapsed = (now - effectiveStart) / 1000 / 60; // minutes
            minRuntimeMet = elapsed >= AUTO_STOP_CONFIG.minRuntimeMinutes;
        }
        
        return {
            timestamp: now.toISOString(),
            mongo: {
                studentsProcessing: mongoCount
            },
            redis: redisStatus,
            workers: workerStatus ? {
                total: workerStatus.totalWorkers,
                running: workerStatus.runningWorkers,
                allUp: workerStatus.allRunning
            } : null,
            autoStop: {
                eligible: false,
                reasons: [],
                stableMinutes: this.stableStartTime 
                    ? Math.floor((now - this.stableStartTime) / 1000 / 60) 
                    : 0,
                minRuntimeMinutes: AUTO_STOP_CONFIG.minRuntimeMinutes,
                minRuntimeMet,
                lastStartTime: lastStart ? lastStart.toISOString() : null
            }
        };
    }

    async evaluateAutoStop(status) {
        // Must have stable job completion (5 min with 0 running, 0 queued)
        if (!this.stableStartTime) {
            const { jobsRunning, jobsQueued, autoStopEnabled, error } = status.redis;
            
            if (error) return { shouldStop: false, reason: 'Redis error' };
            if (!autoStopEnabled) return { shouldStop: false, reason: 'Auto-stop disabled' };

            const autoOffReached = hasReachedTimeOfDay(new Date(), status.redis.autoOffTime);
            const studentsProcessing = status.mongo.studentsProcessing;
            if (autoOffReached && jobsRunning === 0 && jobsQueued === 0 && studentsProcessing === 0) {
                return {
                    shouldStop: true,
                    reason: `Auto-off time reached (${status.redis.autoOffTime}) and system is idle`,
                };
            }

            if (!status.autoStop.minRuntimeMet) return { shouldStop: false, reason: 'Minimum runtime not met' };
            
            // Check if stable (no jobs running AND no jobs queued)
            if (jobsRunning === 0 && jobsQueued === 0) {
                // First time seeing stable state
                this.stableStartTime = new Date();
                console.log('[AutoStop] Jobs stable - starting 5 min timer');
                return { shouldStop: false, reason: 'Timer started', stableMinutes: 0 };
            } else {
                // Jobs still running or queued - reset timer
                if (this.lastJobsRunning !== jobsRunning || this.lastJobsQueued !== jobsQueued) {
                    this.stableStartTime = null;
                }
            }
            
            this.lastJobsRunning = jobsRunning;
            this.lastJobsQueued = jobsQueued;
            
            return { 
                shouldStop: false, 
                reason: jobsRunning > 0 ? 'Jobs still running' : 'Jobs still in queue',
                jobsRunning,
                jobsQueued
            };
        }
        
        // We have a stable start time - check if 5 minutes have passed
        const elapsed = (new Date() - this.stableStartTime) / 1000 / 60;
        const stableMinutes = Math.floor(elapsed);
        
        if (stableMinutes >= AUTO_STOP_CONFIG.stableMinutes) {
            // All conditions met - auto-stop!
            console.log(`[AutoStop] 5+ minutes stable - triggering auto-stop`);
            this.stableStartTime = null; // Reset
            return { 
                shouldStop: true, 
                reason: 'All jobs completed + 5 min stable + auto-stop enabled + min runtime met',
                stableMinutes
            };
        }
        
        return { 
            shouldStop: false, 
            reason: `Waiting for stability (${stableMinutes}/${AUTO_STOP_CONFIG.stableMinutes} min)`,
            stableMinutes
        };
    }

    async executeAutoStop() {
        console.log('[AutoStop] === AUTO-STOP TRIGGERED ===');
        
        const workersResult = await dockerManager.stopWorkers();
        
        await this.redis.set('automation:workers_up', 'false');
        await this.redis.set('automation:main_switch', 'off');
        
        const message = `Auto-stop: ${workersResult.stopped.length} workers stopped. Last job completed at ${new Date().toLocaleTimeString()}.`;
        
        await this.redis.set('automation:auto_stop_reason', message);
        await this.redis.set('automation:last_auto_stop', new Date().toISOString());
        
        console.log(`[AutoStop] ${message}`);
        
        if (this.io) {
            this.io.emit('auto_stop_triggered', {
                message,
                timestamp: new Date().toISOString(),
                workersStopped: workersResult.stopped,
                nextAutoStart: await this.getNextScheduledStart()
            });
        }
        
        return {
            success: true,
            message,
            workersStopped: workersResult.stopped,
            failed: workersResult.failed
        };
    }

    async getNextScheduledStart() {
        const now = new Date();
        let schedules = DEFAULT_SCHEDULED_TIMES;
        try {
            const configuredSchedule = await this.redis.get('automation:daily_schedule');
            const configuredTimes = String(configuredSchedule || '')
                .split(',')
                .map((item) => item.trim())
                .filter((item) => /^\d{2}:\d{2}$/.test(item));
            if (configuredTimes.length > 0) {
                schedules = configuredTimes;
            }
        } catch (e) {
            console.error('[AutoStop] Error reading daily schedule for next start calculation:', e.message);
        }
        
        // Sort schedules chronologically
        schedules.sort((a, b) => {
            const [hA, mA] = a.split(':').map(Number);
            const [hB, mB] = b.split(':').map(Number);
            return (hA * 60 + mA) - (hB * 60 + mB);
        });

        for (const time of schedules) {
            const [h, m] = time.split(':').map(Number);
            const next = new Date(now);
            next.setHours(h, m, 0, 0);
            
            if (next > now) {
                return next.toLocaleString();
            }
        }
        
        // Next day first schedule
        const firstTime = schedules[0] || '06:00';
        const [h, m] = firstTime.split(':').map(Number);
        const next = new Date(now);
        next.setDate(next.getDate() + 1);
        next.setHours(h, m, 0, 0);
        return next.toLocaleString();
    }

    async check() {
        if (!this.isRunning) return;
        
        try {
            const status = await this.getSystemStatus();
            const evaluation = await this.evaluateAutoStop(status);
            
            if (evaluation.shouldStop) {
                await this.executeAutoStop();
            }
        } catch (error) {
            console.error('[AutoStop] Check error:', error.message);
        }
    }

    async emitStatus() {
        if (!this.io) return;
        
        try {
            const status = await this.getSystemStatus();
            this.io.emit('auto_stop_status', status);
        } catch (error) {
            console.error('[AutoStop] Status emit error:', error.message);
        }
    }

    start() {
        if (this.intervalId) return;
        
        console.log('[AutoStop] Starting auto-stop detector...');
        this.isRunning = true;
        
        // Main check loop - every 60 seconds
        this.intervalId = setInterval(() => this.check(), AUTO_STOP_CONFIG.checkIntervalMs);
        
        // Status emission loop - every 30 seconds
        this.statusIntervalId = setInterval(() => this.emitStatus(), AUTO_STOP_CONFIG.emitIntervalMs);
        
        // Run immediately
        this.check();
        this.emitStatus();
        
        console.log('[AutoStop] Detector started - checking every 60s');
    }

    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        if (this.statusIntervalId) {
            clearInterval(this.statusIntervalId);
            this.statusIntervalId = null;
        }
        this.isRunning = false;
        this.stableStartTime = null;
        console.log('[AutoStop] Detector stopped');
    }

    resetStableTimer() {
        this.stableStartTime = null;
        console.log('[AutoStop] Stable timer reset');
    }

    recordStart() {
        this.lastStartTime = new Date();
        this.stableStartTime = null;
        console.log('[AutoStop] Start time recorded, stable timer reset');
    }

    isActive() {
        return this.isRunning;
    }
}

module.exports = { AutoStopDetector, AUTO_STOP_CONFIG };
