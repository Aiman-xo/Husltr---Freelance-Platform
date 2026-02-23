# from django.shortcuts import render

# # Create your views here.
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from .models import Message
# from .serializers import MessageSerializer

# class ChatHistoryView(APIView):
#     def get(self, request, room_name):

#         messages = Message.objects.filter(room_name=room_name).order_by('timestamp')

#         # Optional: Limit to last 50 messages for performance
#         # messages = messages[:50] 

#         serializer = MessageSerializer(messages, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)