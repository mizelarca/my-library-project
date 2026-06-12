from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, DateWidget
from .models import Book, Author, Genre, Status

class BookResource(resources.ModelResource):
    author = fields.Field(
        column_name='Автор',
        attribute='author',
        widget=ForeignKeyWidget(Author, 'name')
    )
    genre = fields.Field(
        column_name='Жанр',
        attribute='genre',
        widget=ForeignKeyWidget(Genre, 'name')
    )
    status = fields.Field(
        column_name='Статус',
        attribute='status',
        widget=ForeignKeyWidget(Status, 'name')
    )
    date_started = fields.Field(
        column_name='Дата начала чтения',
        attribute='date_started',
        widget=DateWidget(format='%d.%m.%Y')
    )
    date_finished = fields.Field(
        column_name='Дата окончания чтения',
        attribute='date_finished',
        widget=DateWidget(format='%d.%m.%Y')
    )
    
    class Meta:
        model = Book
        fields = (
            'title', 'author', 'genre', 'status', 'rating',
            'description', 'format', 'series', 'series_number',
            'notes', 'date_started', 'date_finished'
        )
        export_order = fields
        import_id_fields = ['title', 'author']

