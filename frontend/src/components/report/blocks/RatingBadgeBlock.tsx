const POSITIVE = new Set(['buy', 'overweight', 'strong buy', 'outperform']);
const NEGATIVE = new Set(['sell', 'underweight', 'reduce', 'underperform']);

function ratingClass(rating: string): string {
  const r = rating.trim().toLowerCase();
  if (POSITIVE.has(r)) return 'rating-badge--positive';
  if (NEGATIVE.has(r)) return 'rating-badge--negative';
  return 'rating-badge--neutral';
}

export interface RatingBadgeBlockProps {
  type: 'rating_badge';
  rating: string;
  previous_rating?: string | null;
  change_date?: string | null;
}

export function RatingBadgeBlock({ rating, previous_rating, change_date }: RatingBadgeBlockProps) {
  return (
    <span className={`rating-badge ${ratingClass(rating)}`}>
      {previous_rating ? <s className="rating-badge__prev">{previous_rating}</s> : null}
      <span className="rating-badge__current">{rating}</span>
      {change_date ? <span className="rating-badge__date">{change_date}</span> : null}
    </span>
  );
}
