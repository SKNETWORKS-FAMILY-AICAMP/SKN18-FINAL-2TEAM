from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def index(request):
    """Experiments page view (인증 필수)."""
    context = {
        # 필요한 컨텍스트 데이터 추가
    }
    return render(request, 'experiments/experiment.html', context)
