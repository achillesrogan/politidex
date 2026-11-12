import Link from "next/link";
export default function NotFound() {
  return (<div className="max-w-xl"><h1 className="font-display text-4xl font-black">Page not found</h1><p className="mt-3">This page does not exist or has not been published yet. <Link className="link" href="/">Return home</Link>.</p></div>);
}
