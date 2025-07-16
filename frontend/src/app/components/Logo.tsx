import Image from 'next/image';

export default function Logo() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 40 }}>
      <Image
        src="/logo.png"
        alt="Logo"
        width={40}
        height={40}
        priority
        style={{ borderRadius: '50%' }}
      />
    </div>
  );
} 