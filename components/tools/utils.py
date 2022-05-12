from datetime import datetime

def epoch_to_datetime(epoch_ms_time):
    timestamp = float(epoch_ms_time) / 1000.0
    return datetime.fromtimestamp(timestamp)

def format_datetime_ms(ms_datetime):
    return ms_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')
