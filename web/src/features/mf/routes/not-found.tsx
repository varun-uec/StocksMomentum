import { Link } from 'react-router';
import { EmptyState, buttonClass, useTitle } from '../components/ui';

export default function MfNotFound() {
  useTitle('Page not found');
  return (
    <EmptyState title="This page does not exist" action={<Link to="/mf" className={buttonClass('primary')}>Back to Discover</Link>}>
      The link may be old or mistyped. Fund pages use the AMFI code, for example /mf/funds/122639.
    </EmptyState>
  );
}
