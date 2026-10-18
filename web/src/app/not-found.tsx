import { Link } from 'react-router';
import { PageHeader } from '@/components/shared/Card';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader title="Page not found" subtitle="This address does not match any Wickstreet screen." />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 text-sm">
        <Link to="/" className="text-indigo-600 dark:text-indigo-400 underline">
          Go to the screener
        </Link>
      </div>
    </div>
  );
}
