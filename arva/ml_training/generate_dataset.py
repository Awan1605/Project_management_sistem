"""
Generate Synthetic Dataset for Task Priority Prediction
========================================================
Dataset ini di-generate sesuai skema Task model di Arviga Kanban Board.

Scoring mengikuti bobot dari prompt AI yang sudah ada:
  - Deadline Urgency  : 40%
  - Complexity/Scope  : 25%
  - Dependencies      : 20%
  - Current Progress  : 15%

Output: task_priority_dataset.csv
"""

import csv
import random
import math
import os

random.seed(42)

NUM_ROWS = 2000
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'task_priority_dataset.csv')

# Strategi distribusi: generate skenario dengan distribusi target seimbang
# ~20% Critical (80-100), ~25% High (60-79), ~30% Medium (40-59), ~25% Low (1-39)
SCENARIO_WEIGHTS = {
    'critical': 0.20,  # overdue + urgent + complex
    'high': 0.25,      # near deadline + medium complex
    'medium': 0.30,    # moderate timeline + moderate work
    'low': 0.25,       # far deadline + simple
}

HEADERS = [
    'days_until_due',
    'is_overdue',
    'has_due_date',
    'checklist_total',
    'checklist_done',
    'checklist_ratio',
    'priority_encoded',
    'num_assignees',
    'num_labels',
    'description_len',
    'title_len',
    'task_age_days',
    'status_encoded',
    'priority_score',       # TARGET (1-100)
    'priority_level',       # TARGET LABEL (Critical/High/Medium/Low)
]


def calculate_deadline_score(days_until_due, has_due_date):
    """Hitung skor urgency berdasarkan deadline (0-100)."""
    if not has_due_date:
        return random.uniform(15, 30)

    if days_until_due <= -14:
        return random.uniform(92, 100)
    elif days_until_due <= -7:
        return random.uniform(85, 95)
    elif days_until_due <= -3:
        return random.uniform(78, 90)
    elif days_until_due < 0:
        return random.uniform(70, 85)
    elif days_until_due == 0:
        return random.uniform(65, 80)
    elif days_until_due <= 1:
        return random.uniform(55, 75)
    elif days_until_due <= 3:
        return random.uniform(45, 65)
    elif days_until_due <= 7:
        return random.uniform(30, 50)
    elif days_until_due <= 14:
        return random.uniform(20, 40)
    elif days_until_due <= 30:
        return random.uniform(10, 30)
    else:
        return random.uniform(5, 20)


def calculate_complexity_score(checklist_total, description_len, priority_encoded):
    """Hitung skor complexity (0-100)."""
    # Checklist banyak = task kompleks
    checklist_factor = min(100, checklist_total * 8) if checklist_total > 0 else 20

    # Deskripsi panjang = task detail/kompleks
    desc_factor = min(100, description_len / 15)

    # Priority manual tinggi = dianggap lebih kompleks
    priority_factor = priority_encoded * 20  # p0(4)=80, p1(3)=60, p2(2)=40, p3(1)=20, p4(0)=0

    score = (checklist_factor * 0.35) + (desc_factor * 0.30) + (priority_factor * 0.35)
    return min(100, max(0, score + random.uniform(-8, 8)))


def calculate_dependency_score(num_assignees, num_labels, task_age_days):
    """Hitung skor dependency/impact (0-100)."""
    # Lebih banyak assignee = lebih penting/blocking
    assignee_factor = min(100, num_assignees * 25)

    # Lebih banyak label = lebih cross-cutting
    label_factor = min(100, num_labels * 20)

    # Task lama yang belum selesai = mungkin blocking
    age_factor = min(100, task_age_days * 0.8)

    score = (assignee_factor * 0.40) + (label_factor * 0.25) + (age_factor * 0.35)
    return min(100, max(0, score + random.uniform(-10, 10)))


def calculate_progress_score(checklist_ratio, status_encoded):
    """Hitung skor progress (0-100). Task hampir selesai bisa diprioritaskan."""
    # Task yang sudah 70-90% selesai -> prioritas tinggi (selesaikan dulu)
    if checklist_ratio >= 0.7 and checklist_ratio < 1.0:
        progress_factor = random.uniform(60, 90)
    elif checklist_ratio >= 0.5:
        progress_factor = random.uniform(40, 65)
    elif checklist_ratio >= 0.2:
        progress_factor = random.uniform(25, 50)
    elif checklist_ratio > 0:
        progress_factor = random.uniform(15, 35)
    else:
        progress_factor = random.uniform(10, 30)

    # Status In Progress (1) -> lebih diprioritaskan dari Pending (0)
    # Review (2) -> sedang menunggu
    status_bonus = {0: 0, 1: 15, 2: 10}.get(status_encoded, 0)

    return min(100, max(0, progress_factor + status_bonus + random.uniform(-5, 5)))


def calculate_priority_score(deadline_s, complexity_s, dependency_s, progress_s, scenario):
    """Hitung final priority score (1-100) dengan bobot dan koreksi skenario."""
    raw = (
        deadline_s * 0.40
        + complexity_s * 0.25
        + dependency_s * 0.20
        + progress_s * 0.15
    )

    # Koreksi range berdasarkan skenario agar distribusi seimbang
    # Ini mensimulasikan penilaian LLM yang mempertimbangkan konteks holistik
    if scenario == 'critical':
        # Target: 80-100
        score = 80 + (raw / 100) * 20 + random.uniform(-5, 5)
    elif scenario == 'high':
        # Target: 60-79
        score = 60 + (raw / 100) * 19 + random.uniform(-5, 5)
    elif scenario == 'medium':
        # Target: 40-59
        score = 40 + (raw / 100) * 19 + random.uniform(-5, 5)
    else:  # low
        # Target: 1-39
        score = 1 + (raw / 100) * 38 + random.uniform(-3, 3)

    return max(1, min(100, round(score)))


def get_priority_level(score):
    """Konversi skor ke level prioritas."""
    if score >= 80:
        return 'Critical'
    elif score >= 60:
        return 'High'
    elif score >= 40:
        return 'Medium'
    else:
        return 'Low'


def generate_row(scenario=None):
    """Generate satu baris data berdasarkan skenario."""
    # Pilih skenario jika tidak ditentukan
    if scenario is None:
        scenario = random.choices(
            population=['critical', 'high', 'medium', 'low'],
            weights=[0.20, 0.25, 0.30, 0.25]
        )[0]

    # -- Generate fitur sesuai skenario --
    if scenario == 'critical':
        # Overdue, urgent, complex tasks
        has_due_date = random.choices([1, 0], weights=[0.95, 0.05])[0]
        if has_due_date:
            days_until_due = random.randint(-30, 0)
        else:
            days_until_due = 0
        priority_encoded = random.choices([4, 3, 2], weights=[0.40, 0.40, 0.20])[0]
        checklist_total = random.randint(5, 25)
        num_assignees = random.randint(2, 5)
        num_labels = random.randint(2, 5)
        description_len = random.randint(200, 2000)
        task_age_days = random.randint(14, 180)
        status_encoded = random.choices([0, 1, 2], weights=[0.20, 0.60, 0.20])[0]

    elif scenario == 'high':
        # Near deadline, somewhat complex
        has_due_date = random.choices([1, 0], weights=[0.90, 0.10])[0]
        if has_due_date:
            days_until_due = random.randint(-5, 5)
        else:
            days_until_due = 0
        priority_encoded = random.choices([4, 3, 2, 1], weights=[0.15, 0.35, 0.35, 0.15])[0]
        checklist_total = random.randint(3, 15)
        num_assignees = random.randint(1, 4)
        num_labels = random.randint(1, 4)
        description_len = random.randint(50, 1000)
        task_age_days = random.randint(7, 90)
        status_encoded = random.choices([0, 1, 2], weights=[0.25, 0.50, 0.25])[0]

    elif scenario == 'medium':
        # Moderate timeline, moderate complexity
        has_due_date = random.choices([1, 0], weights=[0.75, 0.25])[0]
        if has_due_date:
            days_until_due = random.randint(3, 20)
        else:
            days_until_due = 0
        priority_encoded = random.choices([3, 2, 1, 0], weights=[0.15, 0.40, 0.30, 0.15])[0]
        checklist_total = random.choices([0, random.randint(1, 5), random.randint(6, 12)], weights=[0.25, 0.50, 0.25])[0]
        num_assignees = random.choices([0, 1, 2, 3], weights=[0.15, 0.45, 0.25, 0.15])[0]
        num_labels = random.choices([0, 1, 2, 3], weights=[0.20, 0.40, 0.25, 0.15])[0]
        description_len = random.randint(0, 600)
        task_age_days = random.randint(1, 45)
        status_encoded = random.choices([0, 1, 2], weights=[0.40, 0.40, 0.20])[0]

    else:  # low
        # Far deadline or no deadline, simple tasks
        has_due_date = random.choices([1, 0], weights=[0.60, 0.40])[0]
        if has_due_date:
            days_until_due = random.randint(14, 60)
        else:
            days_until_due = 0
        priority_encoded = random.choices([2, 1, 0], weights=[0.20, 0.35, 0.45])[0]
        checklist_total = random.choices([0, random.randint(1, 3), random.randint(4, 6)], weights=[0.40, 0.40, 0.20])[0]
        num_assignees = random.choices([0, 1, 2], weights=[0.30, 0.50, 0.20])[0]
        num_labels = random.choices([0, 1, 2], weights=[0.40, 0.40, 0.20])[0]
        description_len = random.randint(0, 300)
        task_age_days = random.randint(0, 20)
        status_encoded = random.choices([0, 1, 2], weights=[0.50, 0.35, 0.15])[0]

    is_overdue = 1 if (has_due_date and days_until_due < 0) else 0

    if checklist_total > 0:
        ratio = random.betavariate(2, 3)
        checklist_done = min(checklist_total, round(checklist_total * ratio))
    else:
        checklist_done = 0

    checklist_ratio = round(checklist_done / checklist_total, 3) if checklist_total > 0 else 0.0

    title_len = random.randint(8, 60)

    # -- Hitung sub-scores --
    deadline_s = calculate_deadline_score(days_until_due, has_due_date)
    complexity_s = calculate_complexity_score(checklist_total, description_len, priority_encoded)
    dependency_s = calculate_dependency_score(num_assignees, num_labels, task_age_days)
    progress_s = calculate_progress_score(checklist_ratio, status_encoded)

    # -- Hitung final score --
    priority_score = calculate_priority_score(deadline_s, complexity_s, dependency_s, progress_s, scenario)
    priority_level = get_priority_level(priority_score)

    return [
        days_until_due,
        is_overdue,
        has_due_date,
        checklist_total,
        checklist_done,
        checklist_ratio,
        priority_encoded,
        num_assignees,
        num_labels,
        description_len,
        title_len,
        task_age_days,
        status_encoded,
        priority_score,
        priority_level,
    ]


def main():
    print(f"Generating {NUM_ROWS} rows...")

    rows = [generate_row() for _ in range(NUM_ROWS)]

    # Statistik
    scores = [r[13] for r in rows]
    levels = [r[14] for r in rows]
    avg = sum(scores) / len(scores)
    min_s = min(scores)
    max_s = max(scores)

    level_counts = {}
    for lv in levels:
        level_counts[lv] = level_counts.get(lv, 0) + 1

    print(f"\nDataset Statistics:")
    print(f"  Total rows  : {NUM_ROWS}")
    print(f"  Score range : {min_s} - {max_s}")
    print(f"  Score avg   : {avg:.1f}")
    print(f"  Distribution:")
    for lv in ['Critical', 'High', 'Medium', 'Low']:
        count = level_counts.get(lv, 0)
        pct = count / NUM_ROWS * 100
        print(f"    {lv:10s}: {count:4d} ({pct:.1f}%)")

    # Write CSV
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows)

    print(f"\nSaved to: {OUTPUT_FILE}")
    print(f"File size: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")


if __name__ == '__main__':
    main()
