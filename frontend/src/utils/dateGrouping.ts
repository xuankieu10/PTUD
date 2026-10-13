import type { ChatSession } from '../types';

export interface GroupedSessions {
  groupName: string;
  sessions: ChatSession[];
}

export function groupSessionsByDate(sessions: ChatSession[]): GroupedSessions[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const sevenDaysAgo = new Date(today);
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const groups: { [key: string]: ChatSession[] } = {
    'Hôm nay': [],
    'Hôm qua': [],
    '7 ngày trước': [],
    'Cũ hơn': [],
  };

  for (const session of sessions) {
    const dateStr = session.updated_at || session.created_at;
    const sessionDate = dateStr ? new Date(dateStr) : new Date();
    const sessionDay = new Date(sessionDate.getFullYear(), sessionDate.getMonth(), sessionDate.getDate());

    if (sessionDay.getTime() === today.getTime()) {
      groups['Hôm nay'].push(session);
    } else if (sessionDay.getTime() === yesterday.getTime()) {
      groups['Hôm qua'].push(session);
    } else if (sessionDay.getTime() >= sevenDaysAgo.getTime()) {
      groups['7 ngày trước'].push(session);
    } else {
      groups['Cũ hơn'].push(session);
    }
  }

  const result: GroupedSessions[] = [];
  const order = ['Hôm nay', 'Hôm qua', '7 ngày trước', 'Cũ hơn'];

  for (const name of order) {
    if (groups[name].length > 0) {
      result.push({
        groupName: name,
        sessions: groups[name],
      });
    }
  }

  return result;
}

export function getTimeGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) {
    return 'Chào buổi sáng!';
  } else if (hour < 18) {
    return 'Chào buổi chiều!';
  } else {
    return 'Chào buổi tối!';
  }
}
