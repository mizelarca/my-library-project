from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('books/', views.book_list, name='book_list'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('book/add/', views.book_add, name='book_add'),
    path('book/<int:book_id>/edit/', views.book_edit, name='book_edit'),
    path('author/add/', views.author_add, name='author_add'),
    path('genre/add/', views.genre_add, name='genre_add'),
    path('book/<int:book_id>/', views.book_detail, name='book_detail'),
    path('profile/', views.profile, name='profile'),
    path('collections/', views.collection_list, name='collection_list'),
    path('collections/create/', views.collection_create, name='collection_create'),
    path('collections/<int:collection_id>/', views.collection_detail, name='collection_detail'),
    path('collections/<int:collection_id>/edit/', views.collection_edit, name='collection_edit'),
    path('collections/<int:collection_id>/delete/', views.collection_delete, name='collection_delete'),
    path('book/<int:book_id>/add-to-collection/', views.add_book_to_collection, name='add_book_to_collection'),
    path('collections/<int:collection_id>/remove/<int:book_id>/', views.remove_book_from_collection, name='remove_book_from_collection'),
    path('collections/<int:collection_id>/add-books/', views.collection_add_books, name='collection_add_books'),
    path('book/<int:book_id>/delete/', views.book_delete, name='book_delete'),
]