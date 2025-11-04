document.addEventListener('DOMContentLoaded', () => {
  const calendarEl = document.getElementById('calendar');
  const btnAuto = document.getElementById('btn-auto');
  const spnAuto = document.getElementById('auto-spinner');

  // 모달/폼 요소
  const addModalEl = document.getElementById('addShiftModal');
  const addModal = addModalEl ? new bootstrap.Modal(addModalEl) : null;
  const fStaff = document.getElementById('fStaff');
  const fBranch = document.getElementById('fBranch');
  const fDate = document.getElementById('fDate');
  const fStart = document.getElementById('fStart');
  const fEnd = document.getElementById('fEnd');
  const addForm = document.getElementById('addShiftForm');

  async function loadStaffOptions() {
    if (!fStaff) return;
    const res = await fetch('/api/staff');
    const staff = await res.json();
    fStaff.innerHTML = staff.map(s => `<option value="${s.id}" data-shift="${s.shift_type}">${s.name} (${s.shift_type==='day'?'주간':'야간'})</option>`).join('');
  }

  if (calendarEl) {
    const calendar = new FullCalendar.Calendar(calendarEl, {
      initialView: 'timeGridWeek',
      locale: 'ko',
      firstDay: 1,
      slotMinTime: '06:00:00',
      slotMaxTime: '26:00:00',
      height: 'auto',
      nowIndicator: true,
      editable: false,
      selectable: true,
      selectMirror: true,
      eventTimeFormat: { hour: '2-digit', minute: '2-digit' },
      headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek' },
      events: '/api/events',

      // 캘린더 구간 선택 → 모달
      select: async (selectionInfo) => {
        await loadStaffOptions();
        const start = selectionInfo.start;
        const end = selectionInfo.end || new Date(start.getTime() + 60 * 60 * 1000);
        fDate.value = start.toISOString().slice(0,10);
        fStart.value = start.toTimeString().slice(0,5);
        fEnd.value = end.toTimeString().slice(0,5);
        addModal.show();
      },

      // 이벤트 클릭 → 삭제
      eventClick: async (info) => {
        if (confirm('이 스케줄을 삭제할까요?')) {
          await fetch('/api/schedule/' + info.event.id, { method: 'DELETE' });
          calendar.refetchEvents();
        }
      }
    });

    calendar.render();

    // 폼 제출 → 생성
    if (addForm) {
      addForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
          staff_id: Number(fStaff.value),
          work_date: fDate.value,
          branch: fBranch.value,
          start_time: fStart.value,
          end_time: fEnd.value
        };
        await fetch('/api/schedule', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        });
        addModal.hide();
        calendar.refetchEvents();
      });
    }

    // 자동 배정 버튼
    if (btnAuto){
      btnAuto.addEventListener('click', async ()=>{
        spnAuto.classList.remove('d-none');
        const now = calendar.getDate();
        const monday = new Date(now);
        const day = monday.getDay(); // Sun=0..Sat=6
        const diff = (day===0? -6 : 1 - day);
        monday.setDate(monday.getDate()+diff);
        const y = monday.getFullYear();
        const m = String(monday.getMonth()+1).padStart(2,'0');
        const d = String(monday.getDate()).padStart(2,'0');
        await fetch('/auto_assign', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ monday: `${y}-${m}-${d}` })
        });
        spnAuto.classList.add('d-none');
        calendar.refetchEvents();
        alert('자동 배정 완료 ✅');
      });
    }
  }
});