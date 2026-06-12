from django import template

register = template.Library()

@register.filter
def ru_plural(value, forms):
    """Возвращает правильную форму слова для русского языка
    Использование: {{ count|ru_plural:"книга,книги,книг" }}
    """
    try:
        value = int(value)
    except (ValueError, TypeError):
        return forms.split(',')[2]  # возвращаем форму множественного числа
    
    forms_list = forms.split(',')
    if len(forms_list) != 3:
        return forms
    
    # Для чисел от 11 до 19 всегда множественное число
    if 11 <= value % 100 <= 19:
        return forms_list[2]
    
    remainder = value % 10
    if remainder == 1:
        return forms_list[0]
    elif 2 <= remainder <= 4:
        return forms_list[1]
    else:
        return forms_list[2]
