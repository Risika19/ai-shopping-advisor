import json
import logging
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .utils import ask_assistant, generate_title
from .models import ChatSession, ChatMessage, MessageFeedback

logger = logging.getLogger(__name__)


def chatbot_view(request):
    if request.method == 'POST':
        return _handle_message(request)
    return _render_chat_page(request)


def _handle_message(request):
    try:
        message = request.POST.get('message', '').strip()
        session_id = request.POST.get('session_id', '')

        if not message:
            return JsonResponse({'response': 'Please enter a message.', 'success': False, 'html': False})

        session = _get_session(request, session_id)
        if not session:
            return JsonResponse({'response': 'Session not found.', 'success': False, 'html': False}, status=404)

        user_msg = ChatMessage.objects.create(session=session, role='user', content=message)

        response_text, success = ask_assistant(message, session=session, user=request.user if request.user.is_authenticated else None)

        ChatMessage.objects.create(session=session, role='assistant', content=response_text)

        if session.messages.count() == 2:
            session.title = generate_title(message)
        session.save(update_fields=['title', 'updated_at'] if session.messages.count() == 2 else ['updated_at'])

        return JsonResponse({
            'response': response_text,
            'success': success,
            'session_id': session.id,
            'session_title': session.title,
            'html': True,
            'timestamp': user_msg.created_at.strftime('%I:%M %p'),
            'message_id': user_msg.pk,
        })
    except Exception as e:
        logger.exception("Error in chatbot_view POST")
        return JsonResponse({
            'response': "I'm sorry, something went wrong. Please try again.",
            'success': False,
            'html': False,
        })


def _render_chat_page(request):
    current_session = _get_or_create_session(request)
    sessions = _get_user_sessions(request)
    grouped = _group_sessions(sessions)
    messages = current_session.messages.all()
    history = [
        {
            'id': m.id,
            'role': m.role,
            'content': m.content,
            'time': m.created_at.strftime('%I:%M %p'),
        }
        for m in messages
    ]
    return render(request, 'chatbot/chatbot.html', {
        'chat_history': json.dumps(history),
        'grouped_sessions': json.dumps(grouped),
        'current_session': current_session,
    })


def _get_session(request, session_id):
    if session_id:
        try:
            return ChatSession.objects.get(id=session_id)
        except (ChatSession.DoesNotExist, ValueError):
            pass
    return _get_or_create_session(request)


def _get_or_create_session(request):
    session_id = request.POST.get('session_id') or request.GET.get('session_id')
    if session_id:
        try:
            return ChatSession.objects.get(id=session_id)
        except (ChatSession.DoesNotExist, ValueError):
            pass

    if request.user.is_authenticated:
        session = ChatSession.objects.filter(user=request.user).first()
        if session:
            return session

    if not request.session.session_key:
        request.session.save()
    key = request.session.session_key
    session = ChatSession.objects.filter(session_key=key).first()
    if session:
        return session

    session = ChatSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or '',
    )
    return session


def _get_user_sessions(request):
    if request.user.is_authenticated:
        return ChatSession.objects.filter(user=request.user)
    if request.session.session_key:
        return ChatSession.objects.filter(session_key=request.session.session_key)
    return ChatSession.objects.none()


def _group_sessions(sessions):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=7)

    groups = {
        'Today': [],
        'Yesterday': [],
        'Previous 7 Days': [],
        'Older': [],
    }

    for s in sessions:
        last_msg = s.messages.order_by('-created_at').first()
        preview = ''
        time_str = ''
        if last_msg:
            preview = last_msg.content[:80]
            time_str = last_msg.created_at.strftime('%I:%M %p')

        entry = {
            'id': s.id,
            'title': s.title,
            'preview': preview,
            'time': time_str,
            'created_at': s.created_at.strftime('%b %d'),
            'message_count': s.messages.count(),
        }

        if s.updated_at >= today_start:
            groups['Today'].append(entry)
        elif s.updated_at >= yesterday_start:
            groups['Yesterday'].append(entry)
        elif s.updated_at >= week_start:
            groups['Previous 7 Days'].append(entry)
        else:
            groups['Older'].append(entry)

    result = [{'label': k, 'sessions': v} for k, v in groups.items() if v]
    return result


@require_POST
def new_chat(request):
    session = ChatSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or '',
        title='New Chat',
    )
    if not request.session.session_key:
        request.session.save()
    return JsonResponse({
        'session_id': session.id,
        'title': session.title,
    })


@require_POST
def delete_all_chats(request):
    sessions = _get_user_sessions(request)
    count = sessions.count()
    sessions.delete()
    new_s = ChatSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or '',
        title='New Chat',
    )
    return JsonResponse({'success': True, 'deleted': count, 'session_id': new_s.id})


def list_sessions(request):
    sessions = _get_user_sessions(request)
    grouped = _group_sessions(sessions)
    return JsonResponse({'groups': grouped})


def get_session(request, session_id):
    session, err_resp = _safe_get_session(request, session_id)
    if err_resp:
        return err_resp
    messages = session.messages.all()
    data = {
        'id': session.id,
        'title': session.title,
        'messages': [
            {
                'id': m.id,
                'role': m.role,
                'content': m.content,
                'time': m.created_at.strftime('%I:%M %p'),
            }
            for m in messages
        ],
    }
    return JsonResponse(data)


@require_POST
def rename_session(request, session_id):
    session, err_resp = _safe_get_session(request, session_id)
    if err_resp:
        return err_resp
    title = request.POST.get('title', '').strip()
    if title:
        session.title = title
        session.save(update_fields=['title'])
        return JsonResponse({'success': True, 'title': title})
    return JsonResponse({'success': False, 'error': 'Title is required.'})


@require_POST
def delete_session(request, session_id):
    session, err_resp = _safe_get_session(request, session_id)
    if err_resp:
        return err_resp
    session.delete()
    return JsonResponse({'success': True})


@require_POST
def regenerate_response(request):
    session_id = request.POST.get('session_id', '')
    session = _get_session(request, session_id)
    if not session:
        return JsonResponse({'error': 'Session not found.'}, status=404)

    messages = list(session.messages.all())
    if len(messages) < 2:
        return JsonResponse({'error': 'No messages to regenerate.'}, status=400)

    last_user_msg = None
    for m in reversed(messages):
        if m.role == 'user':
            last_user_msg = m
            break

    if not last_user_msg:
        return JsonResponse({'error': 'No user message found.'}, status=400)

    session.context = {}
    session.save(update_fields=['context'])

    response_text, success = ask_assistant(
        last_user_msg.content,
        session=session,
        user=request.user if request.user.is_authenticated else None,
    )

    ChatMessage.objects.create(session=session, role='assistant', content=response_text)

    return JsonResponse({
        'response': response_text,
        'success': success,
        'html': True,
        'session_id': session.id,
    })


@require_POST
def submit_feedback(request):
    message_id = request.POST.get('message_id', '')
    rating = request.POST.get('rating', '')

    if not message_id or rating not in ('thumbs_up', 'thumbs_down'):
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    try:
        message = ChatMessage.objects.get(id=message_id)
    except ChatMessage.DoesNotExist:
        return JsonResponse({'error': 'Message not found.'}, status=404)

    if message.role != 'assistant':
        return JsonResponse({'error': 'Can only rate assistant messages.'}, status=400)

    MessageFeedback.objects.update_or_create(
        message=message,
        defaults={'rating': rating},
    )
    return JsonResponse({'success': True})


def export_chat(request, session_id, format='txt'):
    session, err_resp = _safe_get_session(request, session_id)
    if err_resp:
        return err_resp

    messages = session.messages.all()
    lines = []
    for m in messages:
        time_str = m.created_at.strftime('%Y-%m-%d %H:%M')
        role = 'You' if m.role == 'user' else 'ShopAI'
        lines.append(f"[{time_str}] {role}:")
        lines.append(m.content)
        lines.append('')

    content = '\n'.join(lines)
    filename = session.title.replace(' ', '_')[:30]

    if format == 'txt':
        resp = HttpResponse(content, content_type='text/plain; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.txt"'
        return resp

    md_content = f"# {session.title}\n\n"
    for m in messages:
        time_str = m.created_at.strftime('%Y-%m-%d %H:%M')
        role = '**You**' if m.role == 'user' else '**ShopAI**'
        md_content += f"### {role} ({time_str})\n\n{m.content}\n\n---\n\n"

    resp = HttpResponse(md_content, content_type='text/markdown; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{filename}.md"'
    return resp


def _safe_get_session(request, session_id):
    from django.http import JsonResponse as JR
    try:
        session = ChatSession.objects.get(id=session_id)
        _ensure_session_ownership(request, session)
        return session, None
    except (ChatSession.DoesNotExist, ValueError):
        return None, JR({'error': 'Session not found.'}, status=404)
    except PermissionError:
        return None, JR({'error': 'Permission denied.'}, status=403)


def _ensure_session_ownership(request, session):
    if request.user.is_authenticated and session.user and session.user != request.user:
        raise PermissionError("Session does not belong to this user")
    if not request.user.is_authenticated:
        key = request.session.session_key or ''
        if session.session_key and session.session_key != key:
            raise PermissionError("Session does not belong to this user")
