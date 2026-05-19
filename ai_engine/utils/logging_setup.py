import logging
import sys
import os
from datetime import datetime
from pythonjsonlogger import jsonlogger

def setup_logging(name="ai_engine"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Console Handler (Standard Text for human readability in dev)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(console_handler)

    # File Handler (JSON for production)
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"bot.jsonl")
    file_handler = logging.FileHandler(log_file)
    
    # Custom JSON Formatter
    class CustomJsonFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record, record, message_dict):
            super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
            if not log_record.get('timestamp'):
                # this doesn't use record.created, so it is slightly off
                now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                log_record['timestamp'] = now
            if log_record.get('level'):
                log_record['level'] = log_record['level'].upper()
            else:
                log_record['level'] = record.levelname

    formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Global logger instance
logger = setup_logging()
