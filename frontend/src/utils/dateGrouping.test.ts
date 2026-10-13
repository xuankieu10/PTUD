import { describe, it, expect } from 'vitest';
import { groupSessionsByDate, getTimeGreeting } from './dateGrouping';
import type { ChatSession } from '../types';

describe('dateGrouping utils', () => {
  it('groups sessions correctly into Hôm nay, Hôm qua, 7 ngày trước, Cũ hơn', () => {
    const now = new Date();

    const todaySession: ChatSession = {
      id: 1,
      title: 'Hôm nay session',
      created_at: now.toISOString(),
      updated_at: now.toISOString(),
    };

    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdaySession: ChatSession = {
      id: 2,
      title: 'Hôm qua session',
      created_at: yesterday.toISOString(),
      updated_at: yesterday.toISOString(),
    };

    const fourDaysAgo = new Date(now);
    fourDaysAgo.setDate(fourDaysAgo.getDate() - 4);
    const weekSession: ChatSession = {
      id: 3,
      title: 'Trong 7 ngày session',
      created_at: fourDaysAgo.toISOString(),
      updated_at: fourDaysAgo.toISOString(),
    };

    const twentyDaysAgo = new Date(now);
    twentyDaysAgo.setDate(twentyDaysAgo.getDate() - 20);
    const olderSession: ChatSession = {
      id: 4,
      title: 'Cũ hơn session',
      created_at: twentyDaysAgo.toISOString(),
      updated_at: twentyDaysAgo.toISOString(),
    };

    const grouped = groupSessionsByDate([
      todaySession,
      yesterdaySession,
      weekSession,
      olderSession,
    ]);

    expect(grouped).toHaveLength(4);
    expect(grouped[0].groupName).toBe('Hôm nay');
    expect(grouped[0].sessions).toContain(todaySession);
    expect(grouped[1].groupName).toBe('Hôm qua');
    expect(grouped[1].sessions).toContain(yesterdaySession);
    expect(grouped[2].groupName).toBe('7 ngày trước');
    expect(grouped[2].sessions).toContain(weekSession);
    expect(grouped[3].groupName).toBe('Cũ hơn');
    expect(grouped[3].sessions).toContain(olderSession);
  });

  it('omits empty groups (does not show "Cũ hơn" when there are no older sessions)', () => {
    const now = new Date();
    const todaySession: ChatSession = {
      id: 1,
      title: 'Chỉ có hôm nay',
      created_at: now.toISOString(),
    };

    const grouped = groupSessionsByDate([todaySession]);
    expect(grouped).toHaveLength(1);
    expect(grouped[0].groupName).toBe('Hôm nay');
    expect(grouped.some((g) => g.groupName === 'Cũ hơn')).toBe(false);
    expect(grouped.some((g) => g.groupName === 'Hôm qua')).toBe(false);
    expect(grouped.some((g) => g.groupName === '7 ngày trước')).toBe(false);
  });

  it('getTimeGreeting returns appropriate Vietnamese greeting', () => {
    const greeting = getTimeGreeting();
    expect(['Chào buổi sáng!', 'Chào buổi chiều!', 'Chào buổi tối!']).toContain(greeting);
  });
});
