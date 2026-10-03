import { useEffect, useState, type FC } from 'react';
import { Icon, loadIcon } from '@iconify/react';

interface Props {
  icon: string;
}

type IconState = 'loading' | 'loaded' | 'failed';

const ICON_LOAD_TIMEOUT_MS = 10_000;

const GroupNodeIcon: FC<Props> = ({ icon }) => {
  const [loadState, setLoadState] = useState<{ icon: string; state: IconState }>({
    icon,
    state: 'loading',
  });

  useEffect(() => {
    let isMounted = true;
    setLoadState({ icon, state: 'loading' });

    const timeout = window.setTimeout(() => {
      if (isMounted) {
        setLoadState((current) =>
          current.icon === icon && current.state === 'loaded'
            ? current
            : { icon, state: 'failed' },
        );
      }
    }, ICON_LOAD_TIMEOUT_MS);

    void loadIcon(icon)
      .then(() => {
        if (isMounted) {
          window.clearTimeout(timeout);
          setLoadState({ icon, state: 'loaded' });
        }
      })
      .catch(() => {
        if (isMounted) {
          window.clearTimeout(timeout);
          setLoadState({ icon, state: 'failed' });
        }
      });

    return () => {
      isMounted = false;
      window.clearTimeout(timeout);
    };
  }, [icon]);

  const state = loadState.icon === icon ? loadState.state : 'loading';
  if (state === 'failed') {
    const message = `Icon ${icon} could not be loaded`;
    return (
      <span
        className="node-card__group-icon-fallback"
        role="img"
        aria-label={message}
        title={message}
      >
        !
      </span>
    );
  }

  if (state === 'loading') {
    return <span className="node-card__group-icon-placeholder" aria-hidden="true" />;
  }

  return <Icon icon={icon} className="node-card__group-icon" aria-hidden="true" />;
};

export default GroupNodeIcon;
