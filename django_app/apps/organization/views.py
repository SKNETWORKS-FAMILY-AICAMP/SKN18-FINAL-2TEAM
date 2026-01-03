import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import Organization, OrganizationMember, OrganizationInvitation


@login_required
def organization_view(request):
    """
    조직 관리 페이지 뷰
    """
    return render(request, 'accounts/organization.html')


@login_required
@require_http_methods(["GET"])
def organization_list_api(request):
    """
    조직 목록 조회 API
    GET /api/organization/
    """
    user = request.user
    
    # 사용자가 멤버로 속한 조직들 조회 (활성 상태만)
    member_orgs = OrganizationMember.objects.filter(
        user_id=user.user_id,
        organization__status=Organization.Status.ACTIVE
    ).select_related('organization')
    
    organizations_data = []
    for member in member_orgs:
        org = member.organization
        # 사용자의 역할 확인 (소유자인지 멤버인지)
        is_owner = org.created_by_user_id == user.user_id
        
        # 멤버 목록 조회
        members = OrganizationMember.objects.filter(organization=org)
        members_data = []
        other_members_count = 0  # 소유자를 제외한 멤버 수
        
        for mem in members:
            mem_user = mem.user
            if mem_user:
                # 소유자가 아닌 멤버 수 카운트
                if mem.user_id != org.created_by_user_id:
                    other_members_count += 1
                
                members_data.append({
                    'id': str(mem_user.user_id),
                    'name': mem_user.full_name or mem_user.email,
                    'email': mem_user.email,
                    'avatar': mem_user.img_url or '',
                })
        
        organizations_data.append({
            'id': str(org.organization_sid),
            'name': org.organization_name,
            'role': 'owner' if is_owner else 'member',
            'createdAt': org.created_at.strftime('%Y년 %m월 %d일'),
            'members': members_data,
            'memberCount': len(members_data),
            'otherMembersCount': other_members_count,  # 소유자를 제외한 멤버 수
        })
    
    return JsonResponse({
        'success': True,
        'organizations': organizations_data
    })


@login_required
@require_http_methods(["POST"])
def organization_create_api(request):
    """
    조직 생성 API
    POST /api/organization/create/
    """
    try:
        data = json.loads(request.body)
        organization_name = data.get('name', '').strip()
        invite_emails = data.get('invite_emails', [])
        
        if not organization_name:
            return JsonResponse({
                'success': False,
                'error': '조직 이름을 입력해주세요.'
            }, status=400)
        
        # 조직명 중복 체크 (활성 상태인 조직만 체크)
        existing_org = Organization.objects.filter(
            organization_name=organization_name,
            status=Organization.Status.ACTIVE
        ).first()
        
        if existing_org:
            return JsonResponse({
                'success': False,
                'error': '이미 있는 조직 명입니다. 중복되지 않는 조직명을 입력해주세요.'
            }, status=400)
        
        # 조직 생성
        organization = Organization.objects.create(
            organization_name=organization_name,
            created_by_user_id=request.user.user_id
        )
        
        # 생성자를 소유자로 멤버에 추가
        OrganizationMember.objects.create(
            organization=organization,
            user_id=request.user.user_id,
            role=OrganizationMember.Role.OWNER
        )
        
        # 초대 이메일 처리
        created_invitations = []
        invalid_emails = []
        duplicate_invitations = []  # 이미 초대 대기 중인 이메일
        already_members = []  # 이미 멤버인 이메일
        
        from apps.account.models import CustomUser
        
        for email in invite_emails:
            # 이메일 정규화: 소문자 변환 및 공백 제거
            email = email.strip().lower()
            if not email or '@' not in email:
                continue
            
            # zs_user 테이블에서 이메일로 사용자 확인
            try:
                invited_user = CustomUser.objects.get(email__iexact=email)
                # 사용자가 존재하는 경우
                
                # 이미 조직 멤버인지 확인
                existing_member = OrganizationMember.objects.filter(
                    organization=organization,
                    user_id=invited_user.user_id
                ).first()
                
                if existing_member:
                    # 이미 멤버인 경우
                    already_members.append(email)
                    continue
                
                # 중복 초대 방지 (정규화된 이메일로 비교)
                existing_invitation = OrganizationInvitation.objects.filter(
                    organization=organization,
                    email__iexact=email,
                    status=OrganizationInvitation.Status.PENDING
                ).first()
                
                if existing_invitation:
                    # 이미 초대 대기 중인 경우
                    duplicate_invitations.append(email)
                    continue
                
                # 새 초대 생성
                invitation = OrganizationInvitation.objects.create(
                    organization=organization,
                    email=email,  # 정규화된 이메일 저장
                    invited_by_user_id=request.user.user_id,
                    expires_at=timezone.now() + timedelta(days=7)  # 7일 후 만료
                )
                created_invitations.append({
                    'email': invitation.email,
                    'status': invitation.status
                })
                    
            except CustomUser.DoesNotExist:
                # HelixOps에 가입하지 않은 사용자
                invalid_emails.append(email)
            except Exception as e:
                # 기타 오류
                invalid_emails.append(email)
        
        # 가입하지 않은 사용자가 있는 경우 오류 반환
        if invalid_emails:
            return JsonResponse({
                'success': False,
                'error': f'HelixOps에 가입하지 않은 사용자 입니다: {", ".join(invalid_emails)}',
                'invalid_emails': invalid_emails
            }, status=400)
        
        # 응답 메시지 구성
        messages = []
        if created_invitations:
            messages.append(f'{len(created_invitations)}명에게 초대가 발송되었습니다.')
        if duplicate_invitations:
            messages.append(f'{len(duplicate_invitations)}명은 이미 초대 대기 중입니다.')
        if already_members:
            messages.append(f'{len(already_members)}명은 이미 조직 멤버입니다.')
        
        response_message = ' '.join(messages) if messages else '조직이 생성되었습니다.'
        
        return JsonResponse({
            'success': True,
            'organization': {
                'id': str(organization.organization_sid),
                'name': organization.organization_name,
                'role': 'owner',
                'createdAt': organization.created_at.strftime('%Y년 %m월 %d일'),
                'members': [{
                    'id': str(request.user.user_id),
                    'name': request.user.full_name or request.user.email,
                    'email': request.user.email,
                    'avatar': request.user.img_url or '',
                }]
            },
            'invitations': created_invitations,
            'duplicate_invitations': duplicate_invitations,
            'already_members': already_members,
            'message': response_message
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '잘못된 JSON 형식입니다.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def invitation_list_api(request):
    """
    받은 초대 목록 조회 API
    GET /api/organization/invitations/
    zs_organization_invitation 테이블에서 사용자가 받은 초대 목록 조회
    """
    user = request.user
    
    try:
        # 사용자 이메일로 받은 초대 중 대기중인 것만 조회
        # 이메일은 대소문자 구분 없이 비교 (__iexact 사용)
        # 만료되지 않은 초대만 조회 (expires_at이 None이거나 현재 시간보다 이후인 것)
        now = timezone.now()
        
        # 사용자의 모든 가능한 이메일 수집
        user_emails = []
        if user.email:
            user_emails.append(user.email.lower().strip())
        
        # LinkedAccount에서 Google 계정의 이메일도 확인 (provider_user_id가 이메일인 경우)
        try:
            from apps.account.models import LinkedAccount
            linked_accounts = LinkedAccount.objects.filter(
                user=user,
                provider='google'
            )
            # Google의 경우 provider_user_id가 이메일일 수 있지만, 
            # 실제로는 access_token으로 사용자 정보를 가져와야 정확함
            # 일단 현재 이메일만 사용
        except:
            pass
        
        # 사용자 이메일로 초대 조회 (대소문자 구분 없이)
        if not user_emails:
            return JsonResponse({
                'success': True,
                'invitations': [],
                'count': 0
            })
        
        # 여러 이메일로 조회 (OR 조건)
        email_filter = Q()
        for email in user_emails:
            email_filter |= Q(email__iexact=email)
        
        invitations = OrganizationInvitation.objects.filter(
            email_filter,
            status=OrganizationInvitation.Status.PENDING
        ).filter(
            # expires_at이 None이거나 현재 시간보다 이후인 것
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        ).select_related('organization').order_by('-invited_at')
        
        invitations_data = []
        
        for invitation in invitations:
            org = invitation.organization
            inviter = invitation.inviter
            
            # 초대한 사용자 정보
            inviter_data = {
                'name': '알 수 없음',
                'avatar': ''
            }
            
            if inviter:
                inviter_data = {
                    'name': inviter.full_name or inviter.email,
                    'avatar': inviter.img_url or ''
                }
            
            # 조직 멤버 수 조회
            member_count = OrganizationMember.objects.filter(
                organization=org
            ).count()
            
            invitations_data.append({
                'id': str(invitation.id),
                'organization_id': str(org.organization_sid),
                'organization_name': org.organization_name,
                'member_count': member_count,
                'invited_by': inviter_data,
                'invited_at': invitation.invited_at.strftime('%Y년 %m월 %d일'),
                'expires_at': invitation.expires_at.strftime('%Y년 %m월 %d일') if invitation.expires_at else None,
            })
        
        # 만료된 초대는 별도로 업데이트 (백그라운드 작업으로 처리 가능)
        # 현재는 쿼리에서 제외했으므로 별도 업데이트 불필요
        
        return JsonResponse({
            'success': True,
            'invitations': invitations_data,
            'count': len(invitations_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'초대 목록을 불러오는 중 오류가 발생했습니다: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def invitation_respond_api(request, invitation_id):
    """
    초대 수락/거부 API
    POST /api/organization/invitations/{invitation_id}/respond/
    body: {"action": "accept" | "reject"}
    """
    try:
        data = json.loads(request.body)
        action = data.get('action', '').lower()
        
        if action not in ['accept', 'reject']:
            return JsonResponse({
                'success': False,
                'error': 'action은 "accept" 또는 "reject"여야 합니다.'
            }, status=400)
        
        # 초대 조회
        try:
            invitation = OrganizationInvitation.objects.get(
                id=invitation_id,
                email=request.user.email,
                status=OrganizationInvitation.Status.PENDING
            )
        except OrganizationInvitation.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '초대를 찾을 수 없거나 이미 처리되었습니다.'
            }, status=404)
        
        # 만료 확인
        if invitation.is_expired:
            invitation.status = OrganizationInvitation.Status.EXPIRED
            invitation.save()
            return JsonResponse({
                'success': False,
                'error': '만료된 초대입니다.'
            }, status=400)
        
        if action == 'accept':
            # 초대 수락
            org = invitation.organization
            
            # 이미 멤버인지 확인
            existing_member = OrganizationMember.objects.filter(
                organization=org,
                user_id=request.user.user_id
            ).first()
            
            if existing_member:
                # 이미 멤버인 경우 초대만 수락 처리
                invitation.status = OrganizationInvitation.Status.ACCEPTED
                invitation.accepted_at = timezone.now()
                invitation.save()
                
                return JsonResponse({
                    'success': True,
                    'message': '이미 해당 조직의 멤버입니다.',
                    'already_member': True
                })
            
            # 멤버 추가
            OrganizationMember.objects.create(
                organization=org,
                user_id=request.user.user_id,
                role=OrganizationMember.Role.MEMBER
            )
            
            # 초대 상태 업데이트
            invitation.status = OrganizationInvitation.Status.ACCEPTED
            invitation.accepted_at = timezone.now()
            invitation.save()
            
            return JsonResponse({
                'success': True,
                'message': '조직 초대를 수락했습니다.',
                'organization': {
                    'id': str(org.organization_sid),
                    'name': org.organization_name
                }
            })
        
        else:  # reject
            # 초대 거부
            # unique_together 제약조건이 pending만 체크하도록 변경되어
            # 모든 히스토리(pending, accepted, rejected, expired)를 보존할 수 있음
            # pending 레코드를 rejected로 변경 (기존 레코드는 그대로 유지)
            invitation.status = OrganizationInvitation.Status.REJECTED
            invitation.save()
            
            return JsonResponse({
                'success': True,
                'message': '조직 초대를 거부했습니다.'
            })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '잘못된 JSON 형식입니다.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def organization_add_member_api(request, organization_id):
    """
    조직에 멤버 추가 API
    POST /api/organization/{organization_id}/members/
    """
    try:
        data = json.loads(request.body)
        invite_emails = data.get('invite_emails', [])
        
        # 조직 조회
        try:
            organization = Organization.objects.get(organization_sid=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '조직을 찾을 수 없습니다.'
            }, status=404)
        
        # 소유자 권한 확인
        if organization.created_by_user_id != request.user.user_id:
            return JsonResponse({
                'success': False,
                'error': '조직 소유자만 멤버를 추가할 수 있습니다.'
            }, status=403)
        
        from apps.account.models import CustomUser
        
        created_invitations = []
        invalid_emails = []
        duplicate_invitations = []  # 이미 초대 대기 중인 이메일
        already_members = []  # 이미 멤버인 이메일
        
        for email in invite_emails:
            email = email.strip().lower()
            if not email or '@' not in email:
                continue
            
            # zs_user 테이블에서 이메일로 사용자 확인
            try:
                invited_user = CustomUser.objects.get(email__iexact=email)
                
                # 이미 조직 멤버인지 확인
                existing_member = OrganizationMember.objects.filter(
                    organization=organization,
                    user_id=invited_user.user_id
                ).first()
                
                if existing_member:
                    # 이미 멤버인 경우
                    already_members.append(email)
                    continue
                
                # 중복 초대 방지
                existing_invitation = OrganizationInvitation.objects.filter(
                    organization=organization,
                    email__iexact=email,
                    status=OrganizationInvitation.Status.PENDING
                ).first()
                
                if existing_invitation:
                    # 이미 초대 대기 중인 경우
                    duplicate_invitations.append(email)
                    continue
                
                # 새 초대 생성
                invitation = OrganizationInvitation.objects.create(
                    organization=organization,
                    email=email,
                    invited_by_user_id=request.user.user_id,
                    expires_at=timezone.now() + timedelta(days=7)
                )
                created_invitations.append({
                    'email': invitation.email,
                    'status': invitation.status
                })
                    
            except CustomUser.DoesNotExist:
                invalid_emails.append(email)
            except Exception as e:
                invalid_emails.append(email)
        
        if invalid_emails:
            return JsonResponse({
                'success': False,
                'error': f'HelixOps에 가입하지 않은 사용자 입니다: {", ".join(invalid_emails)}',
                'invalid_emails': invalid_emails
            }, status=400)
        
        # 응답 메시지 구성
        messages = []
        if created_invitations:
            messages.append(f'{len(created_invitations)}명에게 초대가 발송되었습니다.')
        if duplicate_invitations:
            messages.append(f'{len(duplicate_invitations)}명은 이미 초대 대기 중입니다.')
        if already_members:
            messages.append(f'{len(already_members)}명은 이미 조직 멤버입니다.')
        
        response_message = ' '.join(messages) if messages else '처리 완료되었습니다.'
        
        return JsonResponse({
            'success': True,
            'invitations': created_invitations,
            'duplicate_invitations': duplicate_invitations,
            'already_members': already_members,
            'message': response_message
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '잘못된 JSON 형식입니다.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def organization_remove_member_api(request, organization_id, member_id):
    """
    조직에서 멤버 제거 API
    DELETE /api/organization/{organization_id}/members/{member_id}/
    """
    try:
        # 조직 조회
        try:
            organization = Organization.objects.get(organization_sid=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '조직을 찾을 수 없습니다.'
            }, status=404)
        
        # 소유자 권한 확인
        if organization.created_by_user_id != request.user.user_id:
            return JsonResponse({
                'success': False,
                'error': '조직 소유자만 멤버를 제거할 수 있습니다.'
            }, status=403)
        
        # 자기 자신은 제거할 수 없음
        if member_id == request.user.user_id:
            return JsonResponse({
                'success': False,
                'error': '자기 자신은 조직에서 제거할 수 없습니다.'
            }, status=400)
        
        # 멤버 조회 및 제거
        try:
            member = OrganizationMember.objects.get(
                organization=organization,
                user_id=member_id
            )
            member_user = member.user
            member_email = member_user.email if member_user else member_id
            
            member.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'{member_email}님이 조직에서 제거되었습니다.'
            })
        except OrganizationMember.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '멤버를 찾을 수 없습니다.'
            }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def organization_delete_api(request, organization_id):
    """
    조직 삭제 API (Soft Delete)
    DELETE /api/organization/{organization_id}/
    - 멤버가 한 명도 없을 때만 삭제 가능
    - status를 'R'로 변경 (soft delete)
    """
    try:
        # 조직 조회
        try:
            organization = Organization.objects.get(
                organization_sid=organization_id,
                status=Organization.Status.ACTIVE
            )
        except Organization.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '조직을 찾을 수 없거나 이미 삭제되었습니다.'
            }, status=404)
        
        # 소유자 권한 확인
        if organization.created_by_user_id != request.user.user_id:
            return JsonResponse({
                'success': False,
                'error': '조직 소유자만 조직을 삭제할 수 있습니다.'
            }, status=403)
        
        # 멤버 수 확인 (소유자 자신을 제외한 멤버 수)
        all_members = OrganizationMember.objects.filter(organization=organization)
        other_members_count = all_members.exclude(user_id=request.user.user_id).count()
        
        if other_members_count > 0:
            return JsonResponse({
                'success': False,
                'error': f'조직에 멤버가 {other_members_count}명 있어 삭제할 수 없습니다. 모든 멤버를 제거한 후 다시 시도해주세요.'
            }, status=400)
        
        # Soft delete: status를 'R'로 변경하고 조직명에 _del 추가
        original_name = organization.organization_name
        organization.organization_name = f'{original_name}_del'
        organization.status = Organization.Status.DELETED
        organization.save()
        
        return JsonResponse({
            'success': True,
            'message': f'"{original_name}" 조직이 삭제되었습니다.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'조직 삭제 중 오류가 발생했습니다: {str(e)}'
        }, status=500)
