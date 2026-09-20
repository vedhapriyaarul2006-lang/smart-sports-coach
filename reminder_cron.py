
from appp import app, send_scheduled_notifications


if __name__ == "__main__":

    with app.app_context():

        print("Smart Sports Coach reminder cron started.")

        send_scheduled_notifications()

        print("Smart Sports Coach reminder cron completed.")

