from django.db import models

# Create your models here.


class Message(models.Model):
    # We use an IntegerField because the User model lives in the other service
    sender_id = models.IntegerField()
    
    # room_name will look like "user_1_user_2"
    room_name = models.CharField(max_length=255, db_index=True)
    
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # This speeds up the specific query of filtering a room + sorting by time
            models.Index(fields=['room_name', '-timestamp']),
        ]
