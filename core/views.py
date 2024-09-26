from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

class HelloWorldView(APIView):
    def get(self, request):
        return Response({"message": "Hello, World!"}, status=status.HTTP_200_OK)

