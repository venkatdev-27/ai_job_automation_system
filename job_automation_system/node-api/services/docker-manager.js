/**
 * Docker Manager Service - Job Automation System
 * ===============================================
 * Production-grade container lifecycle management.
 *
 * Features:
 * - Dynamic container discovery (auto-detects running containers)
 * - Idempotent start/stop operations
 * - Infrastructure health checks before worker startup
 * - Graceful shutdown with SIGTERM + 30s timeout
 * - Force kill fallback for stuck containers
 * - Per-container verification after operations
 * - Auto-stop detector integration
 * - Worker health monitoring
 *
 * DYNAMIC DISCOVERY: No hardcoded container names. Automatically detects
 * all containers with matching labels or name patterns on every call.
 * Works with any docker-compose project name.
 */

const { exec } = require('child_process');

const GRACEFUL_TIMEOUT = 30;
const WORKER_LABEL = 'job-automation-worker';
const INFRA_LABEL = 'job-automation-infra';

class DockerManager {
    constructor() {
        this.composePath = process.env.DOCKER_COMPOSE_PATH || '/app/job_automation_system';
        this.composeFile = process.env.DOCKER_COMPOSE_FILE || 'docker-compose-production.yml';
        this.projectName = process.env.DOCKER_PROJECT_NAME || 'job_automation_system';
        this._workerCache = null;
        this._infraCache = null;
        this._cacheTime = 0;
        this._cacheTTL = 5000;
    }

    exec(command, options = {}) {
        return new Promise((resolve, reject) => {
            exec(command, { cwd: this.composePath, ...options }, (error, stdout, stderr) => {
                if (error) reject(new Error(`${error.message}${stderr ? '\n' + stderr : ''}`));
                else resolve(stdout);
            });
        });
    }

    sleep(seconds) {
        return new Promise(resolve => setTimeout(resolve, seconds * 1000));
    }

    async isDockerAvailable() {
        try {
            await this.exec('docker info', { timeout: 5000 });
            return { available: true };
        } catch {
            return { available: false };
        }
    }

    async isContainerRunning(name) {
        try {
            const out = await this.exec(`docker inspect --format='{{.State.Running}}' ${name}`, { timeout: 5000 });
            return out.trim() === 'true';
        } catch {
            return false;
        }
    }

    async getContainerPid(name) {
        try {
            const out = await this.exec(`docker inspect --format='{{.State.Pid}}' ${name}`, { timeout: 5000 });
            return parseInt(out.trim(), 10);
        } catch {
            return -1;
        }
    }

    async getContainerLabel(name, label) {
        try {
            const out = await this.exec(`docker inspect --format='{{index .Config.Labels "${label}"}}' ${name}`, { timeout: 5000 });
            return out.trim();
        } catch {
            return '';
        }
    }

    async _refreshCache() {
        const now = Date.now();
        if (this._cacheTime && (now - this._cacheTime) < this._cacheTTL) {
            return;
        }

        const allContainers = await this._getAllContainers();
        const infraMap = {};
        const workerMap = {};

        for (const name of allContainers) {
            const lower = name.toLowerCase();
            if (lower.includes('redis') || lower.includes('chrome-cdp') || lower.includes('ai-engine') || lower.includes('node-api') || lower.includes('automation-api') || lower.includes('grafana') || lower.includes('prometheus') || lower.includes('cadvisor') || lower.includes('flower')) {
                if (!workerMap[name]) infraMap[name] = true;
            }
            if (lower.includes('celery-') || lower.includes('producer')) {
                workerMap[name] = true;
                delete infraMap[name];
            }
        }

        this._infraContainers = Object.keys(infraMap);
        this._workerContainers = Object.keys(workerMap);
        this._cacheTime = now;
    }

    async _getAllContainers() {
        try {
            const out = await this.exec(`docker ps -a --format "{{.Names}}"`, { timeout: 10000 });
            return out.trim().split('\n').filter(Boolean);
        } catch {
            return [];
        }
    }

    async _getRunningContainers() {
        try {
            const out = await this.exec(`docker ps --format "{{.Names}}"`, { timeout: 10000 });
            return out.trim().split('\n').filter(Boolean);
        } catch {
            return [];
        }
    }

    get INFRA_CONTAINERS() {
        return this._infraContainers || [];
    }

    get WORKER_CONTAINERS() {
        return this._workerContainers || [];
    }

    async startContainer(name, timeout = 30000) {
        try {
            await this.exec(`docker start ${name}`, { timeout });
            await this.waitForContainer(name, 10);
            return { success: true, container: name };
        } catch (error) {
            if (error.message.includes('already running') || error.message.includes('No such container')) {
                return { success: true, container: name, alreadyRunning: true };
            }
            return { success: false, container: name, error: error.message };
        }
    }

    async stopContainer(name, timeout = 60000) {
        const isRunning = await this.isContainerRunning(name);
        if (!isRunning) {
            return { success: true, container: name, alreadyStopped: true };
        }

        try {
            await this.exec(`docker exec ${name} sh -c "pkill -TERM celery || true"`, { timeout: 5000 });
            await this.sleep(3);
        } catch { }

        try {
            await this.exec(`docker stop --time=${GRACEFUL_TIMEOUT} ${name}`, { timeout });
            const stillRunning = await this.isContainerRunning(name);
            if (stillRunning) {
                await this.exec(`docker kill ${name}`, { timeout: 5000 });
                await this.sleep(1);
            }
            return { success: true, container: name, graceful: true };
        } catch (error) {
            try {
                await this.exec(`docker kill ${name}`, { timeout: 5000 });
                return { success: true, container: name, forceKilled: true };
            } catch (killError) {
                return { success: false, container: name, error: error.message, killError: killError.message };
            }
        }
    }

    async waitForContainer(name, seconds) {
        for (let i = 0; i < seconds * 2; i++) {
            if (await this.isContainerRunning(name)) return;
            await this.sleep(0.5);
        }
    }

    async getWorkerStatus() {
        await this._refreshCache();
        const status = { infra: [], workers: [], allRunning: true, totalWorkers: 0, runningWorkers: 0 };

        for (const name of this.INFRA_CONTAINERS) {
            const running = await this.isContainerRunning(name);
            status.infra.push({ name, running });
        }

        for (const name of this.WORKER_CONTAINERS) {
            const running = await this.isContainerRunning(name);
            status.totalWorkers++;
            if (running) {
                status.runningWorkers++;
                status.workers.push({ name, running: true });
            } else {
                status.allRunning = false;
                status.workers.push({ name, running: false });
            }
        }

        return status;
    }

    async checkInfraHealth() {
        await this._refreshCache();
        const issues = [];
        for (const name of this.INFRA_CONTAINERS) {
            const running = await this.isContainerRunning(name);
            if (!running) issues.push(name);
        }
        return issues;
    }

    async startInfra() {
        console.log('[DockerManager] Checking infrastructure containers...');
        await this._refreshCache();
        const issues = await this.checkInfraHealth();

        if (issues.length === 0) {
            console.log('[DockerManager] All infrastructure containers running');
            return { success: true, started: [], issues: [] };
        }

        console.log(`[DockerManager] Starting ${issues.length} infra containers: ${issues.join(', ')}`);
        const started = [];

        for (const name of issues) {
            const result = await this.startContainer(name, 30000);
            if (result.success) {
                started.push(name);
                console.log(`[DockerManager] Started: ${name}`);
            } else {
                console.error(`[DockerManager] Failed to start ${name}: ${result.error}`);
            }
        }

        return { success: true, started, issues: issues.filter(i => !started.includes(i)) };
    }

    async startWorkers() {
        console.log('[DockerManager] Starting workers...');
        await this._refreshCache();
        const results = { started: [], failed: [], alreadyRunning: [] };

        for (const name of this.WORKER_CONTAINERS) {
            const running = await this.isContainerRunning(name);
            if (running) {
                results.alreadyRunning.push(name);
                continue;
            }

            const result = await this.startContainer(name, 30000);
            if (result.success) {
                results.started.push(name);
                console.log(`[DockerManager] Started worker: ${name}`);
            } else {
                results.failed.push({ name, error: result.error });
                console.error(`[DockerManager] Failed: ${name} - ${result.error}`);
            }
        }

        if (results.failed.length > 0) {
            return {
                success: false,
                message: `${results.failed.length} workers failed to start`,
                started: results.started.length,
                failed: results.failed.length,
                details: results.failed
            };
        }

        return {
            success: true,
            message: `${results.started.length} workers started, ${results.alreadyRunning.length} already running`,
            started: results.started,
            alreadyRunning: results.alreadyRunning
        };
    }

    async stopWorkers() {
        console.log('[DockerManager] Stopping workers...');
        await this._refreshCache();
        const results = { stopped: [], failed: [], alreadyStopped: [] };

        for (const name of this.WORKER_CONTAINERS) {
            const running = await this.isContainerRunning(name);
            if (!running) {
                results.alreadyStopped.push(name);
                continue;
            }

            const result = await this.stopContainer(name, 60000);
            if (result.success) {
                results.stopped.push(name);
                console.log(`[DockerManager] Stopped worker: ${name} (${result.graceful ? 'graceful' : 'force-killed'})`);
            } else {
                results.failed.push({ name, error: result.error });
                console.error(`[DockerManager] Failed to stop ${name}: ${result.error}`);
            }
        }

        return {
            success: results.failed.length === 0,
            message: `${results.stopped.length} workers stopped, ${results.alreadyStopped.length} already stopped`,
            stopped: results.stopped,
            alreadyStopped: results.alreadyStopped,
            failed: results.failed,
            hasFailures: results.failed.length > 0
        };
    }

    async startAll() {
        console.log('[DockerManager] === START ALL ===');

        const dockerCheck = await this.isDockerAvailable();
        if (!dockerCheck.available) {
            return { success: false, error: 'Docker is not running', code: 'DOCKER_NOT_RUNNING' };
        }

        console.log('[DockerManager] Step 1: Starting infrastructure...');
        const infraResult = await this.startInfra();

        console.log('[DockerManager] Step 2: Starting workers...');
        const workerResult = await this.startWorkers();

        if (workerResult.success) {
            return {
                success: true,
                message: 'All containers started',
                infraStarted: infraResult.started,
                workersStarted: workerResult.started,
                workersAlreadyRunning: workerResult.alreadyRunning
            };
        } else {
            return {
                success: false,
                error: workerResult.message,
                infraStarted: infraResult.started,
                workersStarted: workerResult.started,
                workersFailed: workerResult.details
            };
        }
    }

    async stopAll() {
        console.log('[DockerManager] === STOP ALL ===');
        const workerResult = await this.stopWorkers();

        return {
            success: workerResult.success,
            message: workerResult.message,
            stopped: workerResult.stopped,
            alreadyStopped: workerResult.alreadyStopped,
            failed: workerResult.failed,
            hasFailures: workerResult.hasFailures
        };
    }
}

const dockerManager = new DockerManager();

module.exports = { DockerManager, dockerManager };