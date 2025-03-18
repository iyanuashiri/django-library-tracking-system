from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer, LoanNumberSerializer
from rest_framework.decorators import action
from django.utils import timezone
from .tasks import send_loan_notification
from library_system.pagination import DefaultResultsSetPagination

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    pagination_class = DefaultResultsSetPagination

    def get_queryset(self):
        queryset = Book.objects.select_related('author')
        # genre = self.request.query_params.get('genre')
        # if genre:
        #     queryset = queryset.filter(genre=genre)
        return queryset

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    def get_queryset(self):
        queryset = Member.loans.filter(is_returned=False)
        return queryset
    
    @action(detail=True, methods=['get'])
    def loans(self, request, pk=None):
        member = self.get_object()
        loans = member.loans.filter(is_returned=False)
        serializer = LoanSerializer(loans, many=True)
        data = {
            "member_id": serializer.data,
            "username": "Success"
        }
        return Response({'data': serializer.data, 'status': 'Due date extended successfully.',}, status=status.HTTP_200_OK)

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True, methods=['post'])
    def extend_due_date(self, request, pk=None):
        loan = self.get_object()
        serializer = LoanNumberSerializer(data=request.data)
        if serializer.is_valid():
            loan_number = serializer.validated_data['loan_number']
        else:    
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        loan.due_date += timezone.timedelta(days=loan_number)
        loan.save()
        serializer = LoanSerializer(loan)
        return Response({'data': serializer.data, 'status': 'Due date extended successfully.',}, status=status.HTTP_200_OK)
