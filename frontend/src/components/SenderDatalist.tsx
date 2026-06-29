import { useEffect, useState } from 'react'
import { getSenders } from '../api'

interface SenderDatalistProps {
  id: string
}

export default function SenderDatalist({ id }: SenderDatalistProps) {
  const [senderList, setSenderList] = useState<string[]>([])

  useEffect(() => {
    getSenders()
      .then(s => setSenderList(Object.keys(s).sort()))
      .catch(err => console.error('Failed to load senders for datalist', err))
  }, [])

  return (
    <datalist id={id}>
      {senderList.map(s => (
        <option key={s} value={s} />
      ))}
    </datalist>
  )
}
