// FullCalendar + 자동배정 로직
document.addEventListener('DOMContentLoaded', () => {
  const calEl = document.getElementById('calendar');
  if (!calEl) return;

  const calendar = new FullCalendar.Calendar(calEl, {
    initialView: 'timeGridWeek',
    locale: 'ko',
    firstDay: 1,
    slotMinTime: '06:00:00',
    slotMaxTime: '26:00:00',
    height: 'auto',
    nowIndicator: true,
    eventTimeFormat: { hour: '2-digit', minute: '2-digit' },
    events: '/api/events',
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek'
    },
    eventClick(info){
      if(confirm('이 스케줄을 삭제할까요?')){
        fetch('/api/schedule/'+info.event.id, {method:'DELETE'})
          .then(()=>calendar.refetchEvents());
      }
    }
  });
  calendar.render();

  const btn = document.getElementById('btn-auto');
  const spin = document.getElementById('auto-spinner');
  if (btn){
    btn.addEventListener('click', async ()=>{
      spin.classList.remove('d-none');
      // 현재 주의 월요일 계산
      const now = calendar.getDate();
      const monday = new Date(now);
      const day = monday.getDay(); // 0..6 (Sun..Sat)
      const diff = (day===0? -6 : 1 - day); // 월요일로 이동
      monday.setDate(monday.getDate()+diff);
      const y = monday.getFullYear();
      const m = (monday.getMonth()+1).toString().padStart(2,'0');
      const d = monday.getDate().toString().padStart(2,'0');
      await fetch('/auto_assign', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ monday: `${y}-${m}-${d}` })
      });
      spin.classList.add('d-none');
      calendar.refetchEvents();
      alert('자동 배정 완료 ✅');
    });
  }
});
