from celery_app.app import app

print("Sending Naukri task...")
app.send_task('tasks.producer_platform_task.run_naukri', queue='naukri', routing_key='naukri')

print("Sending FoundIt task...")
app.send_task('tasks.producer_platform_task.run_foundit', queue='foundit', routing_key='foundit')

print("Sending LinkedIn task...")
app.send_task('tasks.producer_platform_task.run_linkedin', queue='linkedin', routing_key='linkedin')

print("All tasks sent!")