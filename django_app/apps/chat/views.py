from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json
from .models import RecommendedQuestion, Chat, ChatMessage, ChatReference, ChatMessageFeedback
from .models.papers_models import PaperGraph, PaperNode, PaperEdge, ChatMessagePaperGraph
from .services import generate_concept_graph, generate_ai_response, summarize_conversation_title


@login_required
def index(request):
    """Chat 페이지 렌더링 (인증 필수)"""
    return render(request, 'chat/chat.html')


def recommended_questions(request):
    """추천 질문 API 엔드포인트"""
    # 사용자가 선택한 질문 카테고리(코드, 예: 'bio_q', 'protocal' 등)를 쿼리 파라미터에서 읽어옴
    category = request.GET.get('category', None)
    
    # 기본적으로 활성화된 질문만 조회
    # sql : SELECT * FROM recommended_question WHERE status = 'E'
    queryset = RecommendedQuestion.objects.filter(status='E')
    
    # 카테고리 필터링
    if category:
        queryset = queryset.filter(question_category=category)
    
    # 정렬: sort_order, question_sid 순
    # .values(): 딕셔너리 형태로 데이터 가져오기
    questions = queryset.values('question_sid', 'question_text', 'question_category', 'sort_order')
    
    # 카테고리별로 그룹화 - 디비에서 뽑아온 추천질문목록을 같은 카테고리끼리 묶기
    questions_by_category = {}
    for q in questions:
        cat = q['question_category']
        if cat not in questions_by_category:
            questions_by_category[cat] = []
        questions_by_category[cat].append({
            'id': q['question_sid'],
            'text': q['question_text'],
            'category': q['question_category']
        })
    
    return JsonResponse({
        'questions_by_category': questions_by_category,
        'all_questions': list(questions)
    })


@require_http_methods(["GET"])
def chat_list(request):
    """채팅 목록 API 엔드포인트"""
    section = request.GET.get('section', None)
    
    # 기본적으로 활성화된 채팅만 조회
    queryset = Chat.objects.filter(status='E')
    
    # 섹션별 필터링
    if section == 'favorites':
        queryset = queryset.filter(favorite='Y')
    elif section == 'archived':
        queryset = queryset.filter(archived='Y')
    else:
        # 기본: 보관되지 않은 모든 채팅
        queryset = queryset.filter(archived='N')

    # 정렬: 즐겨찾기 채팅 우선, 그 다음 최신순
    chats = queryset.order_by('-created_at').values(
        'chat_sid', 'title', 'preview', 'favorite', 'archived', 'created_at'
    )

    # 데이터 포맷팅
    items = []
    for chat in chats:
        items.append({
            'id': chat['chat_sid'],
            'title': chat['title'] or '제목 없음',
            'preview': chat['preview'] or '',
            'favorite': chat.get('favorite', 'N'),
            'archived': chat['archived'] == 'Y',
            'created_at': chat['created_at'].isoformat() if chat['created_at'] else None,
        })

    # 즐겨찾기 채팅을 앞으로 이동
    items.sort(key=lambda x: (x['favorite'] != 'Y', x['created_at'] or ''), reverse=True)

    # 카운트 정보 계산 (필터와 관계없이 전체 채팅 기준)
    all_active_chats = Chat.objects.filter(status='E')
    favorites_count = all_active_chats.filter(favorite='Y').count()
    archived_count = all_active_chats.filter(archived='Y').count()

    return JsonResponse({
        'items': items,
        'counts': {
            'favorites': favorites_count,
            'archived': archived_count
        }
    })


@require_http_methods(["GET"])
def chat_detail(request, chat_id):
    """채팅 상세 정보 API 엔드포인트 (메시지 + 참고 문헌)"""
    chat = get_object_or_404(Chat, chat_sid=chat_id, status='E')
    
    # 메시지 조회
    messages = chat.messages.all().order_by('sort_order', 'created_at').values(
        'message_sid', 'role', 'content', 'sort_order', 'created_at'
    )
    
    # 참고 문헌 조회 (채팅 전체 또는 특정 메시지에 연결된 것)
    references = ChatReference.objects.filter(chat=chat).order_by('ref_id', 'created_at').values(
        'reference_sid', 'message_id', 'source', 'badge', 'title', 'description',
        'journal', 'link', 'ref_pubmed_id', 'ref_date', 'ref_authors', 'ref_id'
    )
    
    # 논문 그래프 조회 (메시지별로 연결된 그래프)
    message_graphs = {}
    print(f"[DEBUG] Starting paper graphs query for chat {chat.chat_sid}")
    
    # Debug: Check all ChatMessagePaperGraph records
    all_graphs = ChatMessagePaperGraph.objects.all().select_related('message', 'graph', 'message__chat')
    print(f"[DEBUG] Total ChatMessagePaperGraph records in DB: {all_graphs.count()}")
    for g in all_graphs[:10]:  # Show first 10 for debugging
        msg_sid = g.message.message_sid if g.message else 'None'
        graph_sid = g.graph.graph_sid if g.graph else 'None'
        chat_sid = g.message.chat.chat_sid if g.message and g.message.chat else 'None'
        print(f"[DEBUG]   - Record: message_sid={msg_sid}, graph_sid={graph_sid}, message.chat.chat_sid={chat_sid}")
        
        # Check if this message belongs to the current chat
        if g.message and g.message.chat and g.message.chat.chat_sid == chat.chat_sid:
            print(f"[DEBUG]     -> This graph belongs to the current chat {chat.chat_sid}!")
        else:
            print(f"[DEBUG]     -> This graph belongs to a different chat")
    
    # Debug: Check messages in this chat
    chat_messages = chat.messages.all()
    print(f"[DEBUG] Messages in chat {chat.chat_sid}: {[m.message_sid for m in chat_messages]}")
    
    try:
        # Get message IDs first - use this for more reliable querying
        message_ids = [m.message_sid for m in chat_messages]
        print(f"[DEBUG] Message IDs in chat {chat.chat_sid}: {message_ids}")
        
        # ChatMessagePaperGraph.message is ForeignKey with db_column='message_sid'
        # Django automatically creates message_id field for ForeignKey, but since db_column is set,
        # we need to use the actual column name or the relationship
        if message_ids:
            # Method 1: Use message__pk (primary key lookup) - most reliable
            chat_message_graphs = ChatMessagePaperGraph.objects.filter(
                message__pk__in=message_ids
            ).select_related('graph', 'message').order_by('message__message_sid', 'sort_order', 'created_at')
            
            # Debug: Try different query methods for comparison
            alt_query1 = ChatMessagePaperGraph.objects.filter(
                message__message_sid__in=message_ids
            )
            alt_count1 = alt_query1.count()
            print(f"[DEBUG] Query method 1 (message__message_sid__in): Found {alt_count1} records")
            
            # Method 2: Use raw SQL-like approach with message_id (if Django creates it)
            try:
                alt_query2 = ChatMessagePaperGraph.objects.filter(
                    message_id__in=message_ids
                )
                alt_count2 = alt_query2.count()
                print(f"[DEBUG] Query method 2 (message_id__in): Found {alt_count2} records")
                if alt_count2 > alt_count1:
                    chat_message_graphs = alt_query2.select_related('graph', 'message').order_by('message_id', 'sort_order', 'created_at')
            except Exception as e:
                print(f"[DEBUG] Query method 2 failed: {e}")
            
            # Method 3: Use message__pk
            alt_query3 = ChatMessagePaperGraph.objects.filter(
                message__pk__in=message_ids
            )
            alt_count3 = alt_query3.count()
            print(f"[DEBUG] Query method 3 (message__pk__in): Found {alt_count3} records")
            if alt_count3 > 0:
                chat_message_graphs = alt_query3.select_related('graph', 'message').order_by('message__message_sid', 'sort_order', 'created_at')
        else:
            # Fallback to message__chat if no messages
            chat_message_graphs = ChatMessagePaperGraph.objects.filter(
                message__chat=chat
            ).select_related('graph', 'message').order_by('message_id', 'sort_order', 'created_at')
        
        # Debug: Check if any graphs exist
        graph_count = chat_message_graphs.count()
        print(f"[DEBUG] Found {graph_count} ChatMessagePaperGraph records for chat {chat.chat_sid} (using message_id__in={message_ids})")
        
        # Additional debug: Check each message individually with different approaches
        for msg_id in message_ids:
            # Try different query methods
            try:
                direct_count1 = ChatMessagePaperGraph.objects.filter(message_id=msg_id).count()
            except:
                direct_count1 = -1
            try:
                direct_count2 = ChatMessagePaperGraph.objects.filter(message__message_sid=msg_id).count()
            except:
                direct_count2 = -1
            try:
                direct_count3 = ChatMessagePaperGraph.objects.filter(message__pk=msg_id).count()
            except:
                direct_count3 = -1
            
            print(f"[DEBUG] Message {msg_id}: message_id={direct_count1}, message__message_sid={direct_count2}, message__pk={direct_count3}")
            
            if direct_count1 > 0 or direct_count2 > 0 or direct_count3 > 0:
                print(f"[DEBUG] Message {msg_id} has paper graph(s) - found via one of the query methods")
        
        if graph_count > 0:
            print(f"[DEBUG] Processing {graph_count} paper graphs...")
        
        for msg_graph in chat_message_graphs:
            # Get message_id from the ForeignKey field directly
            message_id = msg_graph.message_id if hasattr(msg_graph, 'message_id') else msg_graph.message.message_sid
            graph_id = msg_graph.graph.graph_sid
            print(f"[DEBUG] Processing graph {graph_id} for message {message_id}")
            
            if message_id not in message_graphs:
                message_graphs[message_id] = []
            
            graph = msg_graph.graph
            # 노드 조회
            nodes = PaperNode.objects.filter(graph=graph).values(
                'paper_id', 'paper_label', 'node_size', 'node_color', 
                'x_position', 'y_position'
            )
            node_count = nodes.count()
            print(f"[DEBUG] Graph {graph_id} has {node_count} nodes")
            
            # 엣지 조회
            edges = PaperEdge.objects.filter(graph=graph).values(
                'source_paper_id', 'target_paper_id'
            )
            edge_count = edges.count()
            print(f"[DEBUG] Graph {graph_id} has {edge_count} edges")
            
            # 노드 포맷팅
            formatted_nodes = []
            for node in nodes:
                formatted_nodes.append({
                    'id': node['paper_id'],
                    'label': node['paper_label'],
                    'size': node['node_size'],
                    'x': float(node['x_position']) if node['x_position'] is not None else 0.0,
                    'y': float(node['y_position']) if node['y_position'] is not None else 0.0,
                    'color': node['node_color'] or '',
                })
            
            # 엣지 포맷팅
            formatted_edges = []
            for edge in edges:
                formatted_edges.append([
                    edge['source_paper_id'],
                    edge['target_paper_id']
                ])
            
            message_graphs[message_id].append({
                'id': graph.graph_sid,
                'title': graph.graph_title or '',
                'description': graph.graph_description or '',
                'nodes': formatted_nodes,
                'edges': formatted_edges,
            })
            print(f"[DEBUG] Added graph {graph_id} to message {message_id}. Total graphs for this message: {len(message_graphs[message_id])}")
        
        print(f"[DEBUG] Final message_graphs keys: {list(message_graphs.keys())}")
        print(f"[DEBUG] Total messages with graphs: {len(message_graphs)}")
        for msg_id, graphs in message_graphs.items():
            print(f"[DEBUG] Message {msg_id} has {len(graphs)} graph(s)")
    except Exception as e:
        print(f"[ERROR] Error loading paper graphs: {e}")
        import traceback
        traceback.print_exc()
    
    # 메시지 포맷팅
    formatted_messages = []
    for msg in messages:
        message_id = msg['message_sid']
        paper_graphs_for_msg = message_graphs.get(message_id, [])
        print(f"[DEBUG] Message {message_id} will have {len(paper_graphs_for_msg)} paper_graphs")
        formatted_messages.append({
            'id': message_id,
            'role': 'user' if msg['role'] == 'U' else 'assistant',
            'content': msg['content'],
            'sort_order': msg['sort_order'],
            'created_at': msg['created_at'].isoformat() if msg['created_at'] else None,
            'paper_graphs': paper_graphs_for_msg,
        })
    
    print(f"[DEBUG] Total formatted messages: {len(formatted_messages)}")
    print(f"[DEBUG] Messages with paper_graphs: {[msg['id'] for msg in formatted_messages if len(msg['paper_graphs']) > 0]}")
    
    # 참고 문헌 포맷팅
    formatted_references = []
    for ref in references:
        # source 변환
        source_map = {'P': 'PubMed', 'W': 'Web', 'N': 'NIH', 'T': 'PROTOCOL'}
        source = source_map.get(ref['source'], ref['source'])
        
        # badge 변환
        badge_map = {'H': '높은 관련성', 'M': '중간 관련성', 'L': '낮은 관련성'}
        badge = badge_map.get(ref['badge'], '')
        
        # journal 변환
        journal_map = {'J': 'Journal', 'B': 'Book', 'R': 'Report', 'P': 'Protocol'}
        journal = journal_map.get(ref['journal'], ref['journal'])
        
        formatted_references.append({
            'id': ref['reference_sid'],
            'message_id': ref['message_id'],
            'source': source,
            'badge': badge,
            'title': ref['title'],
            'description': ref['description'] or '',
            'journal': journal,
            'link': ref['link'] or '',
            'pmid': ref['ref_pubmed_id'] or '',
            'date': ref['ref_date'].strftime('%Y. %m. %d') if ref['ref_date'] else '',
            'authors': ref['ref_authors'] or '',
            'ref_id': ref['ref_id'],  # UI에서 [24], [25]로 표시되는 참고문헌 번호
        })
    
    return JsonResponse({
        'chat': {
            'id': chat.chat_sid,
            'title': chat.title or '제목 없음',
            'preview': chat.preview or '',
            'favorite': chat.favorite == 'Y',
            'archived': chat.archived == 'Y',
            'filter_type': chat.filter_type or '',
            'auto_mode': chat.auto_mode == 'Y',
            'created_at': chat.created_at.isoformat() if chat.created_at else None,
        },
        'messages': formatted_messages,
        'references': formatted_references,
    })


@require_http_methods(["PATCH"])
def update_chat_title(request, chat_id):
    """채팅방 제목 수정 API"""
    from django.utils import timezone

    chat = get_object_or_404(Chat, chat_sid=chat_id, status='E')

    try:
        data = json.loads(request.body)
        new_title = data.get('title', '').strip()

        if not new_title:
            return JsonResponse({'error': '제목을 입력해주세요.'}, status=400)

        if len(new_title) > 50:
            return JsonResponse({'error': '제목은 50자 이내로 입력해주세요.'}, status=400)

        # 제목 업데이트
        chat.title = new_title
        chat.is_title_custom = True  # 사용자가 수정함
        chat.save(update_fields=['title', 'is_title_custom', 'updated_at'])

        return JsonResponse({
            'title': chat.title,
            'updated_at': chat.updated_at.isoformat()
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': '잘못된 요청입니다.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt  # CSRF 검증을 사용하지 않음 (API 호출 가능)
@require_http_methods(["POST"])  # POST 요청만 허용
def graph_summary(request):
    """
    채팅 메시지 내용을 기반으로 Mermaid 그래프 코드를 생성하는 API 엔드포인트
    """
    print(f"[DEBUG] graph_summary() 호출됨")
    print(f"[DEBUG] Request method: {request.method}")
    print(f"[DEBUG] Request body: {request.body.decode('utf-8')[:200] if request.body else 'None'}...")
    
    try:
        data = json.loads(request.body)
        message_content = data.get('message_content', '')
        message_id = data.get('message_id', None)
        
        print(f"[DEBUG] 파싱된 데이터 - message_id: {message_id}, message_content 길이: {len(message_content) if message_content else 0}")
        
        # 메시지 ID가 제공된 경우, DB에서 메시지 조회 및 concept_graph 확인
        message = None
        if message_id:
            try:
                message = ChatMessage.objects.get(message_sid=message_id)
                # DB 메시지의 content를 사용 (더 정확한 데이터)
                message_content = message.content
                print(f"[DEBUG] DB에서 메시지 조회 성공, message_content 길이: {len(message_content) if message_content else 0}")
                
                # DB에 concept_graph가 이미 있으면 바로 반환
                if message.concept_graph:
                    print(f"[DEBUG] DB에 concept_graph 존재, 바로 반환 (길이: {len(message.concept_graph)})")
                    return JsonResponse({
                        'graph': message.concept_graph,
                        'message_id': message_id,
                        'from_cache': True  # DB에서 가져온 것임을 표시
                    })
                else:
                    print(f"[DEBUG] DB에 concept_graph 없음, LLM으로 생성 시작...")
            except ChatMessage.DoesNotExist:
                print(f"[DEBUG] DB에서 메시지 조회 실패 (message_sid={message_id}), 전달된 content 사용")
                # 메시지가 없어도 전달된 content로 진행
                pass
        
        # message_content가 여전히 비어있으면 에러
        if not message_content:
            print(f"[DEBUG] message_content가 비어있음, 400 에러 반환")
            return JsonResponse({
                'error': 'message_content is required'
            }, status=400)
        
        # 실제 ChatMessage 객체가 있으면 사용, 없으면 임시 객체 생성
        if not message:
            class TempMessage:
                def __init__(self, content):
                    self.content = content
            message = TempMessage(message_content)
        
        # Mermaid 그래프 코드 생성 (DB에 없을 때만)
        try:
            print(f"[DEBUG] generate_concept_graph() 호출 시작")
            graph_code = generate_concept_graph(message)
            
            # Mermaid 코드에서 ```mermaid 또는 ``` 제거
            graph_code = graph_code.strip()
            if graph_code.startswith('```'):
                # ```mermaid 또는 ``` 제거
                lines = graph_code.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                graph_code = '\n'.join(lines).strip()
            
            # 실제 ChatMessage 객체인 경우 DB에 저장
            if isinstance(message, ChatMessage) and message_id:
                print(f"[DEBUG] concept_graph를 DB에 저장 중...")
                message.concept_graph = graph_code
                message.save(update_fields=["concept_graph"])
                print(f"[DEBUG] concept_graph DB 저장 완료")
            
            return JsonResponse({
                'graph': graph_code,
                'message_id': message_id,
                'from_cache': False  # 새로 생성한 것임을 표시
            })
        except Exception as e:
            print(f"[ERROR] Error generating graph: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'error': f'Failed to generate graph: {str(e)}',
                'graph': ''  # 빈 그래프 반환
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        print(f"[ERROR] Error in graph_summary: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': f'Internal server error: {str(e)}'
        }, status=500)


# 주석처리: message_concept_graph 함수는 graph_summary와 동일한 기능을 수행하며,
# 현재 프론트엔드 및 백엔드 어디에서도 사용되지 않아 주석처리함.
# 필요시 graph_summary API를 사용하면 됨.
# @require_http_methods(["POST"])
# @csrf_exempt
# def message_concept_graph(request, message_id):
#     """
#     특정 메시지의 concept_graph를 생성하거나 조회하는 API 엔드포인트
#     
#     - 메시지에 concept_graph가 없으면 생성
#     - message.concept_graph = graph_code로 할당
#     - message.save(update_fields=["concept_graph"])로 DB에 저장
#     - 생성된 그래프 코드를 JSON으로 반환
#     """
#     print(f"[DEBUG] message_concept_graph() 호출됨 - message_id: {message_id}")
#     
#     try:
#         # 메시지 조회 (assistant 역할만)
#         message = get_object_or_404(
#             ChatMessage,
#             message_sid=message_id,
#             role='A'  # Assistant만
#         )
#         
#         print(f"[DEBUG] 메시지 조회 성공 - message_sid: {message.message_sid}, role: {message.role}")
#         print(f"[DEBUG] 현재 concept_graph 존재 여부: {bool(message.concept_graph)}")
#         
#         # concept_graph가 없으면 생성
#         if not message.concept_graph:
#             print(f"[DEBUG] concept_graph가 없음, 생성 시작...")
#             try:
#                 graph_code = generate_concept_graph(message)
#                 print(f"[DEBUG] concept_graph 생성 완료, 길이: {len(graph_code) if graph_code else 0}")
#                 
#                 # Mermaid 코드에서 ```mermaid 또는 ``` 제거
#                 graph_code = graph_code.strip()
#                 if graph_code.startswith('```'):
#                     print(f"[DEBUG] 코드 블록 마커 제거 중...")
#                     lines = graph_code.split('\n')
#                     if lines[0].startswith('```'):
#                         lines = lines[1:]
#                     if lines and lines[-1].strip() == '```':
#                         lines = lines[:-1]
#                     graph_code = '\n'.join(lines).strip()
#                     print(f"[DEBUG] 코드 블록 마커 제거 완료, 최종 길이: {len(graph_code)}")
#                 
#                 # DB에 저장
#                 message.concept_graph = graph_code
#                 message.save(update_fields=["concept_graph"])
#                 print(f"[DEBUG] concept_graph DB 저장 완료")
#             except Exception as exc:
#                 print(f"[ERROR] concept_graph 생성 중 오류: {exc}")
#                 import traceback
#                 traceback.print_exc()
#                 return JsonResponse({
#                     'error': f'Failed to generate concept graph: {str(exc)}'
#                 }, status=500)
#         else:
#             print(f"[DEBUG] 기존 concept_graph 사용, 길이: {len(message.concept_graph)}")
#         
#         return JsonResponse({
#             'graph': message.concept_graph,
#             'message_id': message_id
#         })
#         
#     except ChatMessage.DoesNotExist:
#         print(f"[ERROR] 메시지를 찾을 수 없음 - message_id: {message_id}")
#         return JsonResponse({
#             'error': 'Message not found'
#         }, status=404)
#     except Exception as e:
#         print(f"[ERROR] message_concept_graph() 오류: {e}")
#         traceback.print_exc()
#         return JsonResponse({
#             'error': f'Internal server error: {str(e)}'
#         }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def message_feedback(request, message_id):
    """
    메시지에 대한 피드백(좋아요/싫어요)을 저장하는 API 엔드포인트
    """
    try:
        data = json.loads(request.body)
        feedback_type = data.get('feedback_type')  # 'L' for like, 'D' for dislike
        
        if feedback_type not in ['L', 'D']:
            return JsonResponse({
                'error': 'Invalid feedback_type. Must be "L" or "D".'
            }, status=400)
        
        # 메시지 조회
        message = get_object_or_404(ChatMessage, message_sid=message_id)
        
        # 기존 피드백이 있는지 확인 (같은 사용자의 같은 메시지에 대한 피드백)
        # user_id는 CustomUser의 primary key
        user_id = str(request.user.user_id) if request.user.is_authenticated else 'anonymous'
        
        # 기존 피드백 조회 - 같은 사용자가 이미 이 메시지에 피드백을 남겼는지 확인
        existing_feedback = ChatMessageFeedback.objects.filter(
            message=message,
            created_id=user_id
        ).first()
        
        if existing_feedback:
            # 같은 타입의 피드백이면 취소 (삭제)
            if existing_feedback.feedback_type == feedback_type:
                existing_feedback.delete()
                return JsonResponse({
                    'success': True,
                    'action': 'removed',
                    'message': '피드백이 취소되었습니다.'
                })
            else:
                # 다른 타입의 피드백이면 업데이트
                existing_feedback.feedback_type = feedback_type
                existing_feedback.updated_id = user_id
                existing_feedback.save()
                return JsonResponse({
                    'success': True,
                    'action': 'updated',
                    'message': '피드백이 업데이트되었습니다.',
                    'feedback_type': feedback_type
                })
        else:
            # 새로운 피드백 생성
            feedback = ChatMessageFeedback.objects.create(
                message=message,
                feedback_type=feedback_type,
                created_id=user_id,
                updated_id=user_id
            )
            
            return JsonResponse({
                'success': True,
                'action': 'created',
                'message': '피드백이 저장되었습니다.',
                'feedback_id': feedback.feedback_sid,
                'feedback_type': feedback_type
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        print(f"[ERROR] Error in message_feedback: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': f'Internal server error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def toggle_favorite(request, chat_id):
    """
    채팅 favorite 상태를 토글하는 API 엔드포인트
    Y <-> N 전환
    """
    try:
        # 채팅 조회
        chat = get_object_or_404(Chat, chat_sid=chat_id, status='E')

        # favorite 상태 토글
        if chat.favorite == 'Y':
            chat.favorite = 'N'
            action = 'unfavorited'
            message = '즐겨찾기가 해제되었습니다.'
        else:
            chat.favorite = 'Y'
            action = 'favorited'
            message = '즐겨찾기에 추가되었습니다.'

        # 사용자 ID 설정
        user_id = str(request.user.user_id) if request.user.is_authenticated else 'anonymous'
        chat.updated_id = user_id
        chat.save()

        return JsonResponse({
            'success': True,
            'action': action,
            'favorite': chat.favorite,
            'message': message
        })

    except Chat.DoesNotExist:
        return JsonResponse({
            'error': 'Chat not found'
        }, status=404)
    except Exception as e:
        print(f"[ERROR] Error in toggle_favorite: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': f'Internal server error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def toggle_archive(request, chat_id):
    """
    채팅 archived 상태를 토글하는 API 엔드포인트
    Y <-> N 전환
    """
    try:
        # 채팅 조회
        chat = get_object_or_404(Chat, chat_sid=chat_id, status='E')

        # archived 상태 토글
        if chat.archived == 'Y':
            chat.archived = 'N'
            action = 'unarchived'
            message = '보관이 해제되었습니다.'
        else:
            chat.archived = 'Y'
            action = 'archived'
            message = '채팅이 보관되었습니다.'

        # 사용자 ID 설정
        user_id = str(request.user.user_id) if request.user.is_authenticated else 'anonymous'
        chat.updated_id = user_id
        chat.save()

        return JsonResponse({
            'success': True,
            'action': action,
            'archived': chat.archived,
            'message': message
        })

    except Chat.DoesNotExist:
        return JsonResponse({
            'error': 'Chat not found'
        }, status=404)
    except Exception as e:
        print(f"[ERROR] Error in toggle_archive: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': f'Internal server error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def delete_chat(request, chat_id):
    """
    채팅을 삭제하는 API 엔드포인트
    status를 'R' (Removed)로 변경하여 soft delete
    """
    try:
        # 채팅 조회 (이미 삭제된 것도 조회 가능하도록 status 필터 제거)
        chat = get_object_or_404(Chat, chat_sid=chat_id)

        # 이미 삭제된 채팅인지 확인
        if chat.status == 'R':
            return JsonResponse({
                'success': True,
                'message': '이미 삭제된 채팅입니다.',
                'already_deleted': True
            })

        # status를 'R'로 변경
        chat.status = 'R'

        # 사용자 ID 설정
        user_id = str(request.user.user_id) if request.user.is_authenticated else 'anonymous'
        chat.updated_id = user_id
        chat.save()

        return JsonResponse({
            'success': True,
            'message': '채팅이 삭제되었습니다.',
            'chat_id': chat_id
        })

    except Chat.DoesNotExist:
        return JsonResponse({
            'error': 'Chat not found'
        }, status=404)
    except Exception as e:
        print(f"[ERROR] Error in delete_chat: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': f'Internal server error: {str(e)}'
        }, status=500)


def _serialize_message(message):
    """메시지 객체를 JSON 직렬화 가능한 딕셔너리로 변환"""
    return {
        'id': message.message_sid,
        'role': 'user' if message.role == 'U' else 'assistant',
        'content': message.content,
        'sort_order': message.sort_order,
        'created_at': message.created_at.isoformat() if message.created_at else None,
    }


def _serialize_reference(ref):
    """
    참고문헌 객체를 JSON 직렬화 가능한 딕셔너리로 변환

    목적: AI 응답과 함께 참고문헌을 UI에 실시간으로 표시하기 위해
          ChatReference 모델의 DB 코드 값을 사용자가 읽을 수 있는 텍스트로 변환
    """
    # source 변환: DB 코드 -> 표시명 (P=PubMed, W=Web, N=NIH, T=PROTOCOL)
    source_map = {'P': 'PubMed', 'W': 'Web', 'N': 'NIH', 'T': 'PROTOCOL'}
    source = source_map.get(ref.source, ref.source)

    # badge 변환: DB 코드 -> 관련성 텍스트 (H=높음, M=중간, L=낮음)
    badge_map = {'H': '높은 관련성', 'M': '중간 관련성', 'L': '낮은 관련성'}
    badge = badge_map.get(ref.badge, '')

    # journal 변환: DB 코드 -> 표시명 (J=Journal, B=Book, R=Report, P=Protocol)
    journal_map = {'J': 'Journal', 'B': 'Book', 'R': 'Report', 'P': 'Protocol'}
    journal = journal_map.get(ref.journal, ref.journal)

    return {
        'id': ref.reference_sid,
        'message_id': ref.message_id,
        'source': source,
        'badge': badge,
        'title': ref.title,
        'description': ref.description or '',
        'journal': journal,
        'link': ref.link or '',
        'pmid': ref.ref_pubmed_id or '',
        'date': ref.ref_date.strftime('%Y. %m. %d') if ref.ref_date else '',
        'authors': ref.ref_authors or '',
        'ref_id': ref.ref_id,  # UI에서 [24], [25]로 표시되는 참고문헌 번호
    }


@csrf_exempt
@require_http_methods(["POST"])
def chat_messages(request, chat_id=None):
    """
    채팅에 새 메시지를 추가하고 AI 응답 생성

    목적: UI에서 사용자 입력을 받아 LangGraph로 전달하고,
          AI 응답 + 참고문헌을 UI로 반환하는 통합 엔드포인트

    - chat_id가 없으면: 새 채팅 생성 후 메시지 추가 (새 대화 시작)
    - chat_id가 있으면: 기존 채팅에 메시지 추가 (기존 대화 이어가기)

    요구사항:
    - 인증된 사용자만 호출 가능
    - POST 메서드만 허용
    - body: { "content": (메시지 내용) } 필수

    응답: { "chat_id": 123, "messages": [...], "references": [...] }
    """
    # 1. 인증 확인
    if not request.user.is_authenticated:
        return JsonResponse({"error": "unauthorized"}, status=401)

    # 2. 요청 본문 파싱
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    content = (payload.get("content") or "").strip()
    if not content:
        return JsonResponse({"error": "content_required"}, status=400)

    user_id = str(request.user.user_id) if request.user.is_authenticated else 'anonymous'

    # 3. 채팅 조회 또는 생성
    if chat_id:
        # 기존 채팅에 메시지 추가
        chat = get_object_or_404(
            Chat,
            chat_sid=chat_id,
            status='E',
            archived='N',
        )
        # 다음 sort_order 계산
        last_message = chat.messages.order_by('-sort_order').first()
        next_sort_order = (last_message.sort_order + 1) if last_message else 1
    else:
        # 새 채팅 생성
        chat = Chat.objects.create(
            title='새로운 대화',
            preview=content[:200],
            status='E',
            favorite='N',
            archived='N',
            auto_mode='Y',
            created_id=user_id,
            updated_id=user_id,
        )
        next_sort_order = 1

    # 4. 사용자 메시지 생성
    user_message = ChatMessage.objects.create(
        chat=chat,
        role='U',
        content=content,
        sort_order=next_sort_order,
        created_id=user_id,
    )

    # 6. Chat.preview 업데이트
    chat.preview = content[:200]  # 최대 200자
    chat.updated_id = user_id
    chat.save(update_fields=['preview', 'updated_id', 'updated_at'])

    # 7. AI 응답 생성
    try:
        ai_text, citations, scores, reference_type, chat_title = generate_ai_response(chat, content)
    except Exception as exc:
        print(f"[ERROR] AI response generation failed: {exc}")
        import traceback
        traceback.print_exc()
        return JsonResponse(
            {
                "messages": [_serialize_message(user_message)],
                "error": f"AI 응답 생성 실패: {str(exc)}",
            },
            status=201,
        )

    # 8. AI 메시지 생성
    assistant_message = ChatMessage.objects.create(
        chat=chat,
        role='A',
        content=ai_text,
        sort_order=next_sort_order + 1,
        created_id='system',
    )

    # Chat.preview를 AI 응답으로 업데이트
    chat.preview = ai_text[:200]
    chat.save(update_fields=['preview', 'updated_at'])

    # 9. citations를 ChatReference로 저장
    print(f"[DEBUG views.py] citations 개수: {len(citations)}")
    if citations:
        for i, citation in enumerate(citations[:5], 1):
            print(f"[DEBUG views.py citation {i}] title: {citation.get('title', 'N/A')[:50]}, url: {citation.get('url', 'N/A')[:50]}")

    for citation in citations:
        # ref_id는 citation의 'id' 필드 사용 (services.py에서 1부터 생성됨)
        ref_id = citation.get('id', 0)

        # source 매핑
        source_type = citation.get('source_type', '')
        if source_type == 'web':
            source = 'W'  # Web
        elif 'pubmed' in source_type.lower() or citation.get('pmid'):
            source = 'P'  # PubMed
        elif 'protocol' in source_type.lower():
            source = 'T'  # PROTOCOL
        else:
            source = 'P'  # 기본값: PubMed

        # badge 매핑 (score 기반)
        score = citation.get('score', 0.0)
        if score >= 0.8:
            badge = 'H'  # High
        elif score >= 0.5:
            badge = 'M'  # Medium
        else:
            badge = 'L'  # Low

        # journal 매핑
        journal = citation.get('journal', '')
        if journal:
            journal_code = 'J'  # Journal
        else:
            journal_code = 'R'  # Report (기본값)

        # 날짜 처리: year, month, day를 datetime.date로 변환
        ref_date = None
        year = citation.get('year')
        month = citation.get('month')
        day = citation.get('day')
        if year and month and day:
            try:
                from datetime import date
                ref_date = date(int(year), int(month), int(day))
            except (ValueError, TypeError):
                ref_date = None

        ChatReference.objects.create(
            chat=chat,
            message=assistant_message,
            source=source,
            badge=badge,
            title=citation.get('title', f'출처 {ref_id}'),
            description='',
            journal=journal_code,
            link=citation.get('url', ''),
            ref_pubmed_id=citation.get('pmid', ''),
            ref_date=ref_date,  # 수정: year, month, day로부터 생성된 date 객체
            ref_authors=citation.get('authors', ''),
            ref_id=ref_id,  # 참고문헌 번호 (services.py의 id 사용, UI에서 [1], [2], [3]...로 표시됨)
        )

    # 10. Chat.title 업데이트 (첫 메시지에서만, 사용자가 수정하지 않았을 때만)
    # 조건: (1) 첫 메시지이고, (2) 사용자가 수정하지 않았을 때만
    message_count = ChatMessage.objects.filter(chat=chat).count()
    is_first_message = (message_count == 2)  # user + assistant = 2개

    if is_first_message and not chat.is_title_custom:
        # 첫 메시지: 제목 자동 생성 (사용자의 첫 질문 사용)
        try:
            summary = summarize_conversation_title(content)  # GPT-4o-mini 사용
            chat.title = summary
            chat.save(update_fields=['title', 'updated_at'])
            print(f"[INFO] 채팅방 제목 생성: {summary}")
        except Exception as exc:
            print(f"[ERROR] Title summarization failed: {exc}")
            chat.title = "새로운 대화"
            chat.save(update_fields=['title'])
    # LangGraph chat_title은 무시 (첫 메시지 이후에는 제목 변경하지 않음)

    # 11. 참고문헌 조회
    # 목적: AI 응답과 함께 참고문헌을 UI에 즉시 표시하기 위해 조회
    chat_references = ChatReference.objects.filter(
        chat=chat,
        message=assistant_message
    ).order_by('ref_id')

    # 12. 두 메시지 + 참고문헌 반환 (chat_id 포함)
    # 목적: 프론트엔드에서 즉시 메시지와 참고문헌을 렌더링할 수 있도록
    #       chat_id, messages, references를 한 번에 반환
    return JsonResponse(
        {
            "chat_id": chat.chat_sid,  # 새 채팅 생성 시 프론트엔드가 chat_id를 알 수 있도록
            "messages": [
                _serialize_message(user_message),
                _serialize_message(assistant_message),
            ],
            "references": [_serialize_reference(ref) for ref in chat_references]  # 실시간 참고문헌 표시용
        },
        status=201,
    )
